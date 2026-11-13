#!/usr/bin/env python3
"""Switch Achievements: ferramenta de referência para definições de jogo.

  index   mostra o índice: variáveis por binding, plano de leitura e prontidão
  save    avalia saves JSON (bindings save_json, ex.: Ship of Harkinian)
  replay  executa um trace de memória simulada (bindings memory, ex.: MK8, Link's Awakening)

Exemplos:
  python3 tools/sa.py index games/mario_kart_8_deluxe/definition.json
  python3 tools/sa.py save games/ship_of_harkinian/definition.json --save-dir examples/soh/Save
  python3 tools/sa.py replay games/zelda_links_awakening/definition.json examples/traces/la_progress.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sa_core.definition import (  # noqa: E402
    Binding, Confidence, Definition, DefinitionError, Index, Readiness, build_index, load_definition,
)
from sa_core.engine import Engine  # noqa: E402
from sa_core.expr import parse_int  # noqa: E402
from sa_core.notify import RARITY_LABEL, write_notification  # noqa: E402
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
            write_notification(ach, lang, notify_dir)
    for ach in result.rehearsal:
        print(f"... ensaio: '{ach.text('name', lang)}' seria desbloqueada (endereço/valor presumido)")


def cmd_save(index: Index, args: argparse.Namespace) -> int:
    if index.binding.source != "save_json":
        print("este binding não lê saves; use 'replay'", file=sys.stderr)
        return 2
    paths = list(args.save)
    if args.save_dir:
        paths += [args.save_dir / Path(name.split(":", 1)[-1]).name for name in index.binding.files]
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("definition", type=Path)
        p.add_argument("--binding")
        p.add_argument("--lang", default="pt-BR")

    def output(p: argparse.ArgumentParser) -> None:
        p.add_argument("--state", type=Path, help="estado do usuário (histórico, contadores)")
        p.add_argument("--notify-dir", type=Path, help="gera .notify do Ultrahand para cada desbloqueio")
        p.add_argument("--reveal-secrets", action="store_true")

    p_index = sub.add_parser("index", help="mostra o índice da definição")
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

    args = parser.parse_args(argv)
    try:
        definition = load_definition(args.definition)
        if args.command == "replay":
            return cmd_replay(definition, args)
        index = build_index(definition, pick_binding(definition, args.binding, getattr(args, "build", None)))
        if args.command == "index":
            cmd_index(index, args.lang)
            return 0
        return cmd_save(index, args)
    except (DefinitionError, json.JSONDecodeError, OSError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
