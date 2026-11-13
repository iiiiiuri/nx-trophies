"""Carregamento, validação e avaliação de packs de conquistas."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .expr import MISSING, Context, ExprError, eval_condition, eval_value

SUPPORTED_SCHEMA = 1
RARITIES = ("common", "uncommon", "rare", "epic", "legendary")
DEFAULT_XP = {"common": 10, "uncommon": 25, "rare": 50, "epic": 100, "legendary": 250}
MAX_ACHIEVEMENTS = 256


class PackError(ValueError):
    pass


class Status(Enum):
    UNLOCKED = "unlocked"
    LOCKED = "locked"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Achievement:
    id: str
    name: dict[str, str]
    description: dict[str, str]
    xp: int
    rarity: str
    secret: bool
    source: str
    condition: dict[str, Any]
    guard: dict[str, Any] | None
    progress: dict[str, Any] | None
    modes: tuple[str, ...] | None

    def text(self, field_name: str, lang: str) -> str:
        values = getattr(self, field_name)
        return values.get(lang) or values.get("en") or next(iter(values.values()))


@dataclass(frozen=True)
class Source:
    id: str
    type: str
    files: tuple[str, ...]
    aliases: dict[str, str]
    slot_modes: dict[str, dict[str, Any]]
    poll_ms: int


@dataclass(frozen=True)
class Pack:
    schema_version: int
    game_id: str
    game_name: str
    pack_version: str
    sources: dict[str, Source]
    achievements: tuple[Achievement, ...]

    def by_id(self, achievement_id: str) -> Achievement:
        for ach in self.achievements:
            if ach.id == achievement_id:
                return ach
        raise KeyError(achievement_id)


@dataclass(frozen=True)
class SlotResult:
    status: Status
    progress: tuple[int, int] | None
    missing_paths: frozenset[str]


@dataclass(frozen=True)
class Slot:
    label: str
    document: Any


def _require(obj: dict[str, Any], key: str, where: str) -> Any:
    if key not in obj:
        raise PackError(f"{where}: campo obrigatório ausente: {key!r}")
    return obj[key]


def _localized(raw: Any, where: str) -> dict[str, str]:
    if isinstance(raw, str):
        return {"en": raw}
    if isinstance(raw, dict) and raw and all(isinstance(v, str) for v in raw.values()):
        return dict(raw)
    raise PackError(f"{where}: texto deve ser string ou mapa idioma -> string")


def _check_expressions(ach: Achievement, aliases: dict[str, str]) -> None:
    probe = Context(document={}, aliases=aliases)
    try:
        eval_condition(ach.condition, probe)
        if ach.guard:
            eval_condition(ach.guard, probe)
        if ach.progress:
            eval_value(ach.progress["value"], probe)
    except (ExprError, KeyError, TypeError) as exc:
        raise PackError(f"conquista {ach.id!r}: {exc}") from exc


def parse_pack(raw: dict[str, Any]) -> Pack:
    schema = _require(raw, "schema_version", "pack")
    if schema != SUPPORTED_SCHEMA:
        raise PackError(f"schema_version {schema} não suportado (esperado {SUPPORTED_SCHEMA})")

    game = _require(raw, "game", "pack")
    sources: dict[str, Source] = {}
    for source_id, spec in _require(raw, "sources", "pack").items():
        if spec.get("type") != "save_json":
            raise PackError(f"fonte {source_id!r}: tipo {spec.get('type')!r} não suportado por esta ferramenta")
        sources[source_id] = Source(
            id=source_id,
            type=spec["type"],
            files=tuple(_require(spec, "files", f"fonte {source_id!r}")),
            aliases=dict(spec.get("aliases", {})),
            slot_modes=dict(spec.get("slot_modes", {})),
            poll_ms=int(spec.get("poll_ms", 2000)),
        )

    entries = _require(raw, "achievements", "pack")
    if len(entries) > MAX_ACHIEVEMENTS:
        raise PackError(f"pack excede {MAX_ACHIEVEMENTS} conquistas")

    achievements: list[Achievement] = []
    seen: set[str] = set()
    for entry in entries:
        ach_id = _require(entry, "id", "conquista")
        where = f"conquista {ach_id!r}"
        if ach_id in seen:
            raise PackError(f"{where}: id duplicado")
        seen.add(ach_id)

        rarity = entry.get("rarity", "common")
        if rarity not in RARITIES:
            raise PackError(f"{where}: raridade inválida {rarity!r}")
        source = entry.get("source", next(iter(sources), ""))
        if source not in sources:
            raise PackError(f"{where}: fonte desconhecida {source!r}")
        progress = entry.get("progress")
        if progress is not None and ("value" not in progress or "target" not in progress):
            raise PackError(f"{where}: progress exige 'value' e 'target'")

        ach = Achievement(
            id=ach_id,
            name=_localized(_require(entry, "name", where), where),
            description=_localized(_require(entry, "description", where), where),
            xp=int(entry.get("xp", DEFAULT_XP[rarity])),
            rarity=rarity,
            secret=bool(entry.get("secret", False)),
            source=source,
            condition=_require(entry, "condition", where),
            guard=entry.get("guard"),
            progress=progress,
            modes=tuple(entry["modes"]) if "modes" in entry else None,
        )
        _check_expressions(ach, sources[source].aliases)
        achievements.append(ach)

    return Pack(
        schema_version=schema,
        game_id=_require(game, "id", "game"),
        game_name=_require(game, "name", "game"),
        pack_version=str(game.get("pack_version", "0.0.0")),
        sources=sources,
        achievements=tuple(achievements),
    )


def load_pack(path: Path) -> Pack:
    with path.open(encoding="utf-8") as handle:
        return parse_pack(json.load(handle))


def slot_mode(source: Source, slot: Slot) -> str:
    ctx = Context(slot.document, source.aliases)
    for mode, cond in source.slot_modes.items():
        if eval_condition(cond, ctx):
            return mode
    return "vanilla"


def evaluate_slot(ach: Achievement, source: Source, slot: Slot) -> SlotResult:
    ctx = Context(slot.document, source.aliases)
    if ach.modes is not None and slot_mode(source, slot) not in ach.modes:
        return SlotResult(Status.UNSUPPORTED, None, frozenset())
    if ach.guard is not None and not eval_condition(ach.guard, ctx):
        return SlotResult(Status.UNSUPPORTED, None, frozenset(ctx.missing_paths))

    progress = None
    if ach.progress is not None:
        target = int(ach.progress["target"])
        current = eval_value(ach.progress["value"], ctx)
        if current is not MISSING:
            progress = (min(int(current), target), target)

    unlocked = eval_condition(ach.condition, ctx)
    return SlotResult(Status.UNLOCKED if unlocked else Status.LOCKED, progress, frozenset(ctx.missing_paths))


def evaluate(ach: Achievement, source: Source, slots: list[Slot]) -> SlotResult:
    """Combina os slots: desbloqueia se qualquer slot satisfaz; progresso é o maior."""
    results = [evaluate_slot(ach, source, slot) for slot in slots]
    if not results:
        return SlotResult(Status.UNSUPPORTED, None, frozenset())
    if any(r.status is Status.UNLOCKED for r in results):
        status = Status.UNLOCKED
    elif any(r.status is Status.LOCKED for r in results):
        status = Status.LOCKED
    else:
        status = Status.UNSUPPORTED
    progresses = [r.progress for r in results if r.progress is not None]
    progress = max(progresses, key=lambda p: p[0]) if progresses else None
    if status is Status.UNLOCKED and progress is not None:
        progress = (progress[1], progress[1])
    missing = frozenset().union(*(r.missing_paths for r in results))
    return SlotResult(status, progress, missing)
