#!/usr/bin/env python3
"""Avalia um pack de conquistas contra arquivos de save (simulação do motor no PC).

Exemplos:
  python3 tools/sa_eval.py packs/ship_of_harkinian/pack.json --save-dir /caminho/soh/Save
  python3 tools/sa_eval.py packs/ship_of_harkinian/pack.json --save file1.sav --state estado.json --notify-dir notify/
  python3 tools/sa_eval.py packs/ship_of_harkinian/pack.json --save-dir Save --state estado.json --watch
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sa_core.notify import RARITY_LABEL, write_notification  # noqa: E402
from sa_core.pack import Pack, PackError, Slot, Status, evaluate, load_pack, slot_mode  # noqa: E402
from sa_core.store import UserState, level_for_xp, load_state, save_state, xp_for_level  # noqa: E402

STATUS_LABEL = {
    Status.UNLOCKED: "[X]",
    Status.LOCKED: "[ ]",
    Status.UNSUPPORTED: "[?]",
}


def read_slot(path: Path, retries: int = 3, delay: float = 0.3) -> Slot | None:
    """Lê um save tolerando escrita em andamento (o SoH grava o arquivo no lugar)."""
    for attempt in range(retries):
        try:
            with path.open(encoding="utf-8") as handle:
                return Slot(label=path.name, document=json.load(handle))
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, UnicodeDecodeError):
            if attempt + 1 < retries:
                time.sleep(delay)
    print(f"aviso: {path} não é um JSON válido (escrita em andamento ou arquivo corrompido)", file=sys.stderr)
    return None


def collect_save_paths(pack: Pack, saves: list[Path], save_dir: Path | None) -> list[Path]:
    paths = list(saves)
    if save_dir is not None:
        for source in pack.sources.values():
            paths.extend(save_dir / Path(name.split(":", 1)[-1]).name for name in source.files)
    return paths


def describe_slot(pack: Pack, slot: Slot) -> str:
    source = next(iter(pack.sources.values()))
    doc = slot.document
    base = doc.get("sections", {}).get("base", {}).get("data", {})
    stats = doc.get("sections", {}).get("sohStats", {}).get("data", {})
    version = ".".join(str(stats.get(k, "?")) for k in ("buildVersionMajor", "buildVersionMinor", "buildVersionPatch"))
    tenths = stats.get("playTimer", 0) // 2 + stats.get("pauseTimer", 0) // 3
    hours, rem = divmod(tenths // 10, 3600)
    return (
        f"{slot.label}: modo={slot_mode(source, slot)} SoH={version} "
        f"mortes={base.get('deaths', '?')} skulltulas={base.get('inventory', {}).get('gsTokens', '?')} "
        f"tempo={hours}h{rem // 60:02d}m counts={len(stats.get('counts', []))}"
    )


def run_once(pack: Pack, slots: list[Slot], state: UserState | None, lang: str,
             notify_dir: Path | None, reveal: bool, verbose: bool) -> list[str]:
    newly: list[str] = []
    rows: list[str] = []
    labels = RARITY_LABEL.get(lang, RARITY_LABEL["en"])
    earned_xp = 0
    done = 0

    for ach in pack.achievements:
        result = evaluate(ach, pack.sources[ach.source], slots)
        already = state is not None and state.is_unlocked(pack.game_id, ach.id)
        unlocked = already or result.status is Status.UNLOCKED

        if unlocked and not already and state is not None:
            state.unlock(pack.game_id, ach.id, ach.xp)
            newly.append(ach.id)
            if notify_dir is not None:
                write_notification(ach, lang, notify_dir)
        if unlocked:
            earned_xp += ach.xp
            done += 1

        hidden = ach.secret and not unlocked and not reveal
        name = "Conquista secreta" if hidden else ach.text("name", lang)
        desc = "???" if hidden else ach.text("description", lang)
        status = Status.UNLOCKED if unlocked else result.status
        progress = ""
        if result.progress is not None and not hidden:
            progress = f" ({result.progress[0]}/{result.progress[1]})"
        marker = " NOVA!" if ach.id in newly else ""
        rows.append(f"  {STATUS_LABEL[status]} {name}{progress} · {ach.xp} XP · {labels[ach.rarity]}{marker}\n"
                    f"      {desc}")
        if verbose and result.missing_paths:
            rows.append(f"      campos ausentes: {', '.join(sorted(result.missing_paths))}")

    total = len(pack.achievements)
    xp = state.total_xp if state is not None else earned_xp
    level = level_for_xp(xp)
    print(f"\n{pack.game_name} — {done}/{total} conquistas ({100 * done // max(total, 1)}%)")
    print(f"XP: {xp} · Nível {level} (próximo em {xp_for_level(level + 1)} XP)\n")
    print("\n".join(rows))
    print("\nLegenda: [X] desbloqueada · [ ] bloqueada · [?] não suportada neste save/versão")
    return newly


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--save", type=Path, action="append", default=[], help="arquivo de save (repetível)")
    parser.add_argument("--save-dir", type=Path, help="pasta com os saves declarados no pack (ex.: soh/Save)")
    parser.add_argument("--state", type=Path, help="estado do usuário (habilita histórico e detecção de novos)")
    parser.add_argument("--notify-dir", type=Path, help="gera .notify do Ultrahand para cada novo desbloqueio")
    parser.add_argument("--lang", default="pt-BR")
    parser.add_argument("--reveal-secrets", action="store_true")
    parser.add_argument("--watch", action="store_true", help="reavalia quando um save muda")
    parser.add_argument("--verbose", action="store_true", help="mostra campos ausentes no save")
    args = parser.parse_args(argv)

    try:
        pack = load_pack(args.pack)
    except (PackError, json.JSONDecodeError, OSError) as exc:
        print(f"erro no pack: {exc}", file=sys.stderr)
        return 2

    paths = collect_save_paths(pack, args.save, args.save_dir)
    if not paths:
        print("informe --save ou --save-dir", file=sys.stderr)
        return 2

    state = load_state(args.state) if args.state else None
    last_mtimes: dict[Path, float] = {}

    while True:
        mtimes = {p: p.stat().st_mtime for p in paths if p.exists()}
        if mtimes != last_mtimes:
            last_mtimes = mtimes
            slots = [s for s in (read_slot(p) for p in paths) if s is not None]
            if not slots:
                print("nenhum save encontrado", file=sys.stderr)
            else:
                for slot in slots:
                    print(describe_slot(pack, slot))
                newly = run_once(pack, slots, state, args.lang, args.notify_dir, args.reveal_secrets, args.verbose)
                if state is not None and args.state:
                    save_state(state, args.state)
                for ach_id in newly:
                    ach = pack.by_id(ach_id)
                    print(f">>> CONQUISTA DESBLOQUEADA: {ach.text('name', args.lang)} (+{ach.xp} XP)")
        if not args.watch:
            return 0 if last_mtimes else 1
        time.sleep(next(iter(pack.sources.values())).poll_ms / 1000)


if __name__ == "__main__":
    sys.exit(main())
