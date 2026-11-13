#!/usr/bin/env python3
"""Switch Achievements: ferramenta de referência para definições de jogo.

Cada jogo é um arquivo games/<id>.json na estrutura padrão; não há registro manual.

  list      lista os jogos e a prontidão das conquistas
  validate  valida games/*.json (estrutura, índices, title IDs)
  new       cria games/<id>.json a partir do esqueleto padrão
  detect    mostra qual jogo/binding o console usaria para title ID + build ID
  index     mostra o índice: variáveis por binding, plano de leitura e prontidão
  save      avalia saves JSON (bindings save_json, ex.: Ship of Harkinian)
  replay    executa um trace de memória simulada (bindings memory, ex.: MK8, Link's Awakening)
  build     monta dist/sd/ (overlay, ícones, definições, som) para copiar ao cartão
  device    fala com o Switch pela rede local (FTP), enquanto o sysmodule não existe

Exemplos:
  python3 tools/sa.py validate
  python3 tools/sa.py new super_mario_odyssey --name "Super Mario Odyssey" --title-id 0100000000010000
  python3 tools/sa.py index mario_kart_8_deluxe
  python3 tools/sa.py save ship_of_harkinian --save-dir examples/soh/Save
  python3 tools/sa.py replay zelda_links_awakening examples/traces/la_progresso.json
  python3 tools/sa.py device install
  python3 tools/sa.py device sync
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sa_core.assets import AssetError, icon_key  # noqa: E402
from sa_core.catalog import (  # noqa: E402
    GAMES_DIR, Catalog, check_definition, game_files, load_catalog, new_definition, resolve_game_path,
)
from sa_core.device import DeviceError, FtpDevice, connect, load_endpoint  # noqa: E402
from sa_core.images import ImageError  # noqa: E402
from sa_core.layout import (  # noqa: E402
    DEFAULT_ICON, DEVICE_CACHE, DIST_SD, SD_OVERLAY, SD_PROFILE, SD_ROOT, SD_STATE, SD_SOUND, SOH_SAVE,
    UH_NOTIFICATIONS, UH_SOUND, UH_SOUND_BACKUP, progress_file, ultrahand_icon_file,
)
from sa_core.progress import game_view, profile_view  # noqa: E402
from sa_core.sdcard import build_sd  # noqa: E402
from sa_core.definition import (  # noqa: E402
    Achievement, Binding, Confidence, Definition, DefinitionError, Index, Readiness, build_index, load_definition,
    parse_definition,
)
from sa_core.engine import Engine  # noqa: E402
from sa_core.expr import parse_int  # noqa: E402
from sa_core.notify import (  # noqa: E402
    RARITY_LABEL, build_notification, notification_name, test_notification, write_notification,
)
from sa_core.sources import FakeProcess, FileSource, MemorySource, Snapshot  # noqa: E402
from sa_core.store import UserState, level_for_xp, load_state, save_state, xp_for_level  # noqa: E402

READINESS_LABEL = {
    Readiness.LIVE: "ativa",
    Readiness.REHEARSAL: "ensaio",
    Readiness.PENDING: "a descobrir",
    Readiness.UNSUPPORTED: "sem suporte",
}
CONFIDENCE_LABEL = {
    Confidence.VERIFIED: "verificado",
    Confidence.COMMUNITY: "comunidade",
    Confidence.ASSUMED: "presumido",
    Confidence.TO_DISCOVER: "a descobrir",
}


def pick_binding(definition: Definition, binding_id: str | None, build_id: str | None) -> Binding:
    if build_id:
        binding = definition.binding_for_build(build_id)
        if binding is None:
            raise DefinitionError(f"nenhum binding para o build {build_id}; jogo sem suporte nesta versão")
        return binding
    if binding_id:
        if binding_id not in definition.bindings:
            raise DefinitionError(f"binding desconhecido {binding_id!r}")
        return definition.bindings[binding_id]
    return next(iter(definition.bindings.values()))


def cmd_index(index: Index, lang: str) -> None:
    d, b = index.definition, index.binding
    print(f"{d.text(lang)}  [{d.kind}]  title_ids={', '.join(d.title_ids) or '-'}")
    print(f"binding: {b.id} ({b.source}) — {b.label}")
    if b.build_ids:
        print(f"builds: {', '.join(b.build_ids)}")
    print("conteúdo: " + ", ".join(f"{k}={len(v)}" for k, v in d.content.items()))

    print("\nvariáveis observadas:")
    for inst in sorted(index.instances.values(), key=lambda i: i.name):
        if inst.offset is not None:
            where = f"{'[' + inst.pointer + ']' if inst.pointer else inst.region}+0x{inst.offset:X}"
        else:
            where = inst.path or "-"
        print(f"  {inst.name:<38} {inst.type:<4} {CONFIDENCE_LABEL[inst.confidence]:<11} {where}")

    if b.pointers:
        print("\nponteiros:")
        for p in b.pointers.values():
            chain = "".join(f"[" for _ in p.chain) + p.region + "".join(f"+0x{o:X}]" for o in p.chain)
            print(f"  {p.id}: {chain}")
    if index.read_plan:
        print(f"\nplano de leitura por tick ({len(index.read_plan)} bloco(s), a cada {b.poll_ms} ms):")
        for block in index.read_plan:
            print(f"  {block.anchor:<14} +0x{block.offset:X} ({block.size} bytes): {len(block.variables)} variáveis")

    print("\nconquistas:")
    counts: dict[Readiness, int] = {}
    for ach in index.achievements:
        level = index.readiness[ach.id]
        counts[level] = counts.get(level, 0) + 1
        reason = f"  <- {index.blockers[ach.id][0]}" if index.blockers[ach.id] and level < Readiness.LIVE else ""
        print(f"  {READINESS_LABEL[level]:<12} {ach.id:<34} {ach.text('name', lang)}{reason}")
    print("\nresumo: " + ", ".join(f"{READINESS_LABEL[k]}={v}" for k, v in sorted(counts.items(), reverse=True)))


def print_report(index: Index, engine: Engine, state: UserState, snapshots: list[Snapshot],
                 lang: str, reveal: bool) -> None:
    labels = RARITY_LABEL.get(lang, RARITY_LABEL["en"])
    game_id = index.definition.game_id
    done = 0
    rows = []
    for ach in index.achievements:
        level = index.readiness[ach.id]
        unlocked = state.is_unlocked(game_id, ach.id)
        done += unlocked
        hidden = ach.secret and not unlocked and not reveal
        name = "Conquista secreta" if hidden else ach.text("name", lang)
        marker = "[X]" if unlocked else ("[ ]" if level >= Readiness.REHEARSAL else "[-]")
        progress = engine.progress(ach, snapshots)
        prog = f" ({progress[0]}/{progress[1]})" if progress and not hidden else ""
        note = "" if level is Readiness.LIVE else f" · {READINESS_LABEL[level]}"
        rows.append(f"  {marker} {name}{prog} · {ach.xp} XP · {labels[ach.rarity]}{note}")
    total = len(index.achievements)
    xp = state.xp_for(game_id)
    level = level_for_xp(state.xp_for())
    print(f"\n{index.definition.text(lang)} — {done}/{total} ({100 * done // max(total, 1)}%) · {xp} XP neste jogo")
    print(f"perfil: {state.xp_for()} XP · nível {level} (próximo em {xp_for_level(level + 1)} XP)\n")
    print("\n".join(rows))
    print("\nLegenda: [X] desbloqueada · [ ] bloqueada · [-] aguardando descoberta de endereço")


def announce(index: Index, result, lang: str, notify_dir: Path | None) -> None:
    for ach in result.unlocked:
        print(f">>> CONQUISTA DESBLOQUEADA: {ach.text('name', lang)} (+{ach.xp} XP)")
        if notify_dir is not None:
            write_notification(ach, lang, notify_dir, icon_key(index.definition.game_id, ach))
    for ach in result.rehearsal:
        print(f"... ensaio: '{ach.text('name', lang)}' seria desbloqueada (endereço/valor presumido)")


def save_paths(index: Index, save_dir: Path) -> list[Path]:
    return [save_dir / Path(name.split(":", 1)[-1]).name for name in index.binding.files]


def cmd_save(index: Index, args: argparse.Namespace) -> int:
    if index.binding.source != "save_json":
        print("este binding não lê saves; use 'replay'", file=sys.stderr)
        return 2
    paths = list(args.save)
    if args.save_dir:
        paths += save_paths(index, args.save_dir)
    state = load_state(args.state) if args.state else UserState()
    engine = Engine(index, state)
    source = FileSource(index, paths)
    last: dict[Path, float] = {}
    while True:
        mtimes = {p: p.stat().st_mtime for p in paths if p.exists()}
        if mtimes != last:
            last = mtimes
            snapshots = source.read()
            for s in snapshots:
                print(f"{s.label}: modo={engine.mode_of(s)}")
            result = engine.tick(snapshots)
            announce(index, result, args.lang, args.notify_dir)
            print_report(index, engine, state, snapshots, args.lang, args.reveal_secrets)
            if args.state:
                save_state(state, args.state)
        if not args.watch:
            return 0 if last else 1
        time.sleep(index.binding.poll_ms / 1000)


def load_trace(path: Path) -> tuple[FakeProcess, dict]:
    with path.open(encoding="utf-8") as handle:
        trace = json.load(handle)
    regions = {name: (parse_int(r["base"]), parse_int(r["size"])) for name, r in trace["regions"].items()}
    return FakeProcess(regions), trace


def apply_writes(process: FakeProcess, writes: list[dict]) -> None:
    for w in writes:
        value = w["value"]
        process.write_value(process.address(w["addr"]), w["type"], parse_int(value) if isinstance(value, str) else value)


def cmd_replay(definition: Definition, args: argparse.Namespace) -> int:
    process, trace = load_trace(args.trace)
    build_id = trace.get("build_id")
    binding = pick_binding(definition, args.binding, build_id)
    index = build_index(definition, binding)
    if binding.source != "memory":
        print("este binding não lê memória; use 'save'", file=sys.stderr)
        return 2
    print(f"trace: {args.trace.name} · build {build_id} -> binding {binding.id} · {len(trace['ticks'])} ticks")
    state = load_state(args.state) if args.state else UserState()
    engine = Engine(index, state)
    source = MemorySource(index, process)
    apply_writes(process, trace.get("initial", []))
    snapshots: list[Snapshot] = []
    for number, tick in enumerate(trace["ticks"], start=1):
        apply_writes(process, tick.get("writes", []))
        snapshots = source.read()
        result = engine.tick(snapshots)
        if args.verbose or result.unlocked or result.rehearsal:
            print(f"tick {number}" + (f": {tick['label']}" if tick.get("label") else ""))
        announce(index, result, args.lang, args.notify_dir)
    print(f"\nleituras de memória: {source.read_calls} em {len(trace['ticks'])} ticks")
    print_report(index, engine, state, snapshots, args.lang, args.reveal_secrets)
    if args.state:
        save_state(state, args.state)
    return 0


def cmd_list(catalog: Catalog, lang: str) -> int:
    for game_id, definition in sorted(catalog.games.items()):
        counts = {label: 0 for label in READINESS_LABEL.values()}
        latest = list(definition.bindings.values())[-1]
        for level in build_index(definition, latest).readiness.values():
            counts[READINESS_LABEL[level]] += 1
        titles = ",".join(definition.title_ids) or "-"
        builds = sum(len(b.build_ids) for b in definition.bindings.values())
        summary = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        print(f"{game_id:<26} {definition.kind:<9} {titles:<17} bindings={len(definition.bindings)} "
              f"builds={builds} conquistas={len(definition.achievements)} ({summary})")
    for problem in catalog.problems:
        print(f"inválido: {problem}", file=sys.stderr)
    return 1 if catalog.problems else 0


def cmd_validate(paths: list[Path]) -> int:
    if paths:
        problems = [p for path in paths for p in check_definition(path)[1]]
        checked = len(paths)
    else:
        catalog = load_catalog()
        problems = catalog.problems
        checked = len(game_files())
    for problem in problems:
        print(f"erro: {problem}", file=sys.stderr)
    print(f"{checked} arquivo(s) verificados, {len(problems)} problema(s)")
    return 1 if problems else 0


def cmd_detect(title_id: str, build_id: str) -> int:
    definition, binding = load_catalog().detect(title_id, build_id)
    if definition is None:
        print(f"title ID {title_id}: nenhum jogo em games/*.json")
        return 1
    if binding is None:
        print(f"{definition.game_id}: build {build_id} sem binding (jogo conhecido, versão sem suporte)")
        return 1
    print(f"{definition.game_id} -> binding {binding.id}")
    return 0


def cmd_build(out: Path) -> int:
    result = build_sd(out)
    print(f"{len(result.files)} arquivo(s) em {out}")
    for relative in sorted({f.rsplit('/', 1)[0] for f in result.files}):
        count = sum(1 for f in result.files if f.rsplit('/', 1)[0] == relative)
        print(f"  sdmc:/{relative}/ ({count})")
    if not result.overlay:
        print("overlay não compilado; veja overlay/README.md")
    return 0


def cmd_device(args: argparse.Namespace) -> int:
    try:
        endpoint = load_endpoint(
            host=args.host, port=args.port, user=args.user, password=args.password, config=args.config,
        )
        device = connect(endpoint)
    except DeviceError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    try:
        command = args.device_command
        if command == "probe":
            return _device_probe(device, endpoint.host, endpoint.port)
        if command == "install":
            return _device_install(device, with_sound=not args.no_sound)
        if command == "restore-sound":
            return _device_restore_sound(device)
        if command == "notify":
            return _device_notify(device, args.file)
        if command == "pull":
            return _device_pull(device, args.into or DEVICE_CACHE / "ship_of_harkinian")
        return _device_sync(device, args)
    except DeviceError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    finally:
        device.close()


def _device_probe(device: FtpDevice, host: str, port: int) -> int:
    print(f"conectado em {host}:{port}")
    base = device.base()
    print("sdmc:/ no FTP: /" + "/".join(base))
    checks = (
        ("Switch Achievements", SD_ROOT),
        ("notificações do Ultrahand", UH_NOTIFICATIONS),
        ("saves do Ship of Harkinian", SOH_SAVE),
    )
    ok = True
    for label, path in checks:
        try:
            found = device.locate(path)
        except DeviceError:
            ok = ok and path == SD_ROOT
            print(f"{label}: ausente (sdmc:/{path})")
        else:
            listed = ", ".join(found.names) or "vazia"
            print(f"{label}: sdmc:/{path} ({listed})")
    print("overlay: " + ("instalado" if device.exists(SD_OVERLAY) else "não instalado"))
    print("som de conquista: " + ("instalado" if device.exists(SD_SOUND) else "não instalado"))
    return 0 if ok else 1


def _device_install(device: FtpDevice, with_sound: bool) -> int:
    result = build_sd(DIST_SD, with_sound=with_sound)
    if with_sound and not device.exists(UH_SOUND_BACKUP):
        original = device.read(UH_SOUND)
        ours = (DIST_SD / UH_SOUND).read_bytes()
        if original is not None and original != ours:
            device.write(UH_SOUND_BACKUP, original)
            print(f"som original do Ultrahand salvo em sdmc:/{UH_SOUND_BACKUP}")
    for relative in result.files:
        device.write(relative, (DIST_SD / relative).read_bytes())
    print(f"{len(result.files)} arquivo(s) enviados")
    if not result.overlay:
        print("overlay não compilado: nada foi para sdmc:/switch/.overlays/ (veja overlay/README.md)")
    if with_sound:
        print("O Ultrahand carrega os sons ao abrir; feche e abra o menu dele (ou reinicie) para ouvir o novo.")
    return 0


def _device_restore_sound(device: FtpDevice) -> int:
    original = device.read(UH_SOUND_BACKUP)
    if original is None:
        print(f"sem backup em sdmc:/{UH_SOUND_BACKUP}", file=sys.stderr)
        return 1
    device.write(UH_SOUND, original)
    print("som de notificação do Ultrahand restaurado")
    return 0


def _device_notify(device: FtpDevice, path: Path | None) -> int:
    if path is None:
        if not device.exists(ultrahand_icon_file(DEFAULT_ICON)):
            print("aviso: ícone ainda não está no SD; rode 'device install'", file=sys.stderr)
        name = notification_name(DEFAULT_ICON)
        data = json.dumps(test_notification(), ensure_ascii=False).encode()
    else:
        name = path.name
        data = path.read_bytes()
    remote = device.write(f"{UH_NOTIFICATIONS}/{name}", data)
    print(f"enviado {remote}")
    print("O Ultrahand lê e apaga esse arquivo. O overlay precisa estar ativo.")
    return 0


def _device_pull(device: FtpDevice, into: Path) -> int:
    saved = device.pull_saves(into)
    if not saved:
        print(f"nenhum .sav em sdmc:/{SOH_SAVE}", file=sys.stderr)
        return 1
    for path in saved:
        print(f"{path.name} ({path.stat().st_size} bytes) -> {path}")
    return 0


def _pull_binding_files(device: FtpDevice, game_id: str, binding: Binding) -> list[Path]:
    local: list[Path] = []
    for remote in binding.files:
        relative = remote.split(":/", 1)[-1].lstrip("/")
        data = device.read(relative)
        if data is None:
            continue
        target = DEVICE_CACHE / game_id / Path(relative).name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        local.append(target)
    return local


def _device_sync(device: FtpDevice, args: argparse.Namespace) -> int:
    """Lê os saves e o estado do SD, avalia todos os jogos e publica estado, progresso e toasts."""
    raw_state = device.read(SD_STATE)
    state = UserState.from_json(json.loads(raw_state)) if raw_state else UserState()
    print(f"estado no SD: {len(state.unlocked)} conquista(s)" if raw_state else "estado no SD: novo")
    catalog = load_catalog()
    if catalog.problems:
        for problem in catalog.problems:
            print(f"erro: {problem}", file=sys.stderr)
        return 2

    views = []
    unlocked: list[tuple[Index, Achievement]] = []
    for game_id, definition in sorted(catalog.games.items()):
        index = build_index(definition, next(iter(definition.bindings.values())))
        snapshots: list[Snapshot] = []
        if index.binding.source == "save_json":
            local = _pull_binding_files(device, game_id, index.binding)
            if local:
                engine = Engine(index, state)
                snapshots = FileSource(index, local).read()
                for snapshot in snapshots:
                    print(f"{game_id}/{snapshot.label}: modo={engine.mode_of(snapshot)}")
                result = engine.tick(snapshots)
                unlocked += [(index, ach) for ach in result.unlocked]
                announce(index, result, args.lang, None)
                print_report(index, engine, state, snapshots, args.lang, args.reveal_secrets)
        views.append(game_view(index, state, snapshots, args.lang))

    device.write(SD_STATE, json.dumps(state.to_json(), ensure_ascii=False, indent=2).encode())
    for view in views:
        device.write(progress_file(view["game"]), json.dumps(view, ensure_ascii=False).encode())
    profile = profile_view(state, views)
    device.write(SD_PROFILE, json.dumps(profile, ensure_ascii=False).encode())
    print(f"\npublicado: estado, perfil e progresso de {len(views)} jogo(s) em sdmc:/{SD_ROOT}/")

    if args.no_notify or not unlocked:
        print("nenhuma notificação enviada" if unlocked else "nenhuma conquista nova")
        return 0
    for index, ach in unlocked:
        key = icon_key(index.definition.game_id, ach)
        payload = json.dumps(build_notification(ach, args.lang), ensure_ascii=False).encode()
        device.write(f"{UH_NOTIFICATIONS}/{notification_name(key)}", payload)
        print(f"toast: {ach.text('name', args.lang)} ({key})")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    path = GAMES_DIR / f"{args.game_id}.json"
    if path.exists():
        print(f"erro: {path} já existe", file=sys.stderr)
        return 2
    raw = new_definition(args.game_id, args.name, title_id=args.title_id, build_id=args.build_id,
                         save_file=args.save_file)
    parse_definition(raw)
    path.write_text(json.dumps(raw, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"criado {path.relative_to(GAMES_DIR.parent)}; edite e rode: python3 tools/sa.py validate")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("game", help="id do jogo (ex.: mario_kart_8_deluxe) ou caminho do .json")
        p.add_argument("--binding")
        p.add_argument("--lang", default="pt-BR")

    def output(p: argparse.ArgumentParser) -> None:
        p.add_argument("--state", type=Path, help="estado do usuário (histórico, contadores)")
        p.add_argument("--notify-dir", type=Path, help="gera .notify do Ultrahand para cada desbloqueio")
        p.add_argument("--reveal-secrets", action="store_true")

    p_list = sub.add_parser("list", help="lista os jogos de games/*.json")
    p_list.add_argument("--lang", default="pt-BR")

    p_validate = sub.add_parser("validate", help="valida games/*.json (ou os arquivos indicados)")
    p_validate.add_argument("paths", nargs="*", type=Path)

    p_detect = sub.add_parser("detect", help="qual jogo e binding o console usaria")
    p_detect.add_argument("title_id")
    p_detect.add_argument("build_id")

    p_new = sub.add_parser("new", help="cria games/<id>.json com a estrutura padrão")
    p_new.add_argument("game_id")
    p_new.add_argument("--name", required=True)
    p_new.add_argument("--title-id")
    p_new.add_argument("--build-id")
    p_new.add_argument("--save-file", help="jogo homebrew lido por save JSON (ex.: Save/file1.sav)")

    p_index = sub.add_parser("index", help="mostra o índice de um jogo")
    common(p_index)
    p_index.add_argument("--build", help="seleciona o binding pelo build ID")

    p_save = sub.add_parser("save", help="avalia saves JSON")
    common(p_save)
    output(p_save)
    p_save.add_argument("--save", type=Path, action="append", default=[])
    p_save.add_argument("--save-dir", type=Path)
    p_save.add_argument("--watch", action="store_true")

    p_replay = sub.add_parser("replay", help="executa um trace de memória simulada")
    common(p_replay)
    output(p_replay)
    p_replay.add_argument("trace", type=Path)
    p_replay.add_argument("--verbose", action="store_true")

    p_device = sub.add_parser("device", help="testa no Switch por FTP na rede local")
    device_sub = p_device.add_subparsers(dest="device_command", required=True)

    def device_conn(p: argparse.ArgumentParser) -> None:
        p.add_argument("--host", help="IP do Switch na rede local")
        p.add_argument("--port", type=int, help="porta do FTP (padrão 5000, ou a do device.local.json)")
        p.add_argument("--user")
        p.add_argument("--password")
        p.add_argument("--config", type=Path, help="JSON com host, port, user e password")

    p_probe = device_sub.add_parser("probe", help="confere o que já está no SD")
    device_conn(p_probe)
    p_install = device_sub.add_parser("install", help="envia overlay, ícones, definições e som")
    device_conn(p_install)
    p_install.add_argument("--no-sound", action="store_true", help="mantém o som de notificação do Ultrahand")
    p_restore = device_sub.add_parser("restore-sound", help="volta o som original do Ultrahand")
    device_conn(p_restore)
    p_notify = device_sub.add_parser("notify", help="envia um toast de teste ao Ultrahand")
    device_conn(p_notify)
    p_notify.add_argument("--file", type=Path, help="um .notify pronto; sem isso, manda o toast de teste")
    p_pull = device_sub.add_parser("pull", help="baixa sdmc:/switch/soh/Save/*.sav")
    device_conn(p_pull)
    p_pull.add_argument("--into", type=Path, help="pasta local (padrão device-cache/ship_of_harkinian)")
    p_sync = device_sub.add_parser("sync", help="avalia os saves e publica estado, tela e toasts no console")
    device_conn(p_sync)
    p_sync.add_argument("--lang", default="pt-BR")
    p_sync.add_argument("--reveal-secrets", action="store_true")
    p_sync.add_argument("--no-notify", action="store_true", help="atualiza a tela sem mandar toasts")

    p_build = sub.add_parser("build", help="monta dist/sd/, o espelho do cartão SD")
    p_build.add_argument("--out", type=Path, default=DIST_SD)

    args = parser.parse_args(argv)
    try:
        if args.command == "device":
            return cmd_device(args)
        if args.command == "build":
            return cmd_build(args.out)
        if args.command == "list":
            return cmd_list(load_catalog(), args.lang)
        if args.command == "validate":
            return cmd_validate(args.paths)
        if args.command == "detect":
            return cmd_detect(args.title_id, args.build_id)
        if args.command == "new":
            return cmd_new(args)
        definition = load_definition(resolve_game_path(args.game))
        if args.command == "replay":
            return cmd_replay(definition, args)
        index = build_index(definition, pick_binding(definition, args.binding, getattr(args, "build", None)))
        if args.command == "index":
            cmd_index(index, args.lang)
            return 0
        return cmd_save(index, args)
    except (DefinitionError, AssetError, ImageError, json.JSONDecodeError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
