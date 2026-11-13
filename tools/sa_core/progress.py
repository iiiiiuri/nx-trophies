"""O que a tela do console mostra: um JSON por jogo e um perfil.

O overlay só lê e desenha; textos já vêm no idioma escolhido, secretas já
vêm escondidas e o ícone já vem resolvido. Quem gera é o PC hoje e, depois,
o sysmodule, com a mesma estrutura.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .assets import shown_icon_key
from .definition import Index, Readiness
from .engine import Engine
from .notify import RARITY_LABEL
from .sources import Snapshot
from .store import UserState, level_for_xp, xp_for_level

VIEW_VERSION = 1
SECRET_TEXT = {
    "pt-BR": ("Conquista secreta", "Continue jogando para descobrir."),
    "en": ("Secret achievement", "Keep playing to find out."),
}
STATUS = {
    Readiness.LIVE: "live",
    Readiness.REHEARSAL: "rehearsal",
    Readiness.PENDING: "pending",
    Readiness.UNSUPPORTED: "unsupported",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def game_view(index: Index, state: UserState, snapshots: list[Snapshot], lang: str) -> dict[str, Any]:
    definition = index.definition
    game_id = definition.game_id
    engine = Engine(index, state)
    labels = RARITY_LABEL.get(lang, RARITY_LABEL["en"])
    secret_name, secret_desc = SECRET_TEXT.get(lang, SECRET_TEXT["en"])
    items = []
    for ach in index.achievements:
        unlocked = state.is_unlocked(game_id, ach.id)
        hidden = ach.secret and not unlocked
        record = state.unlocked.get(f"{game_id}/{ach.id}", {})
        progress = None if hidden else engine.progress(ach, snapshots)
        items.append({
            "id": ach.id,
            "name": secret_name if hidden else ach.text("name", lang),
            "description": secret_desc if hidden else ach.text("description", lang),
            "icon": shown_icon_key(game_id, ach, unlocked),
            "xp": ach.xp,
            "rarity": labels[ach.rarity],
            "secret": ach.secret,
            "unlocked": unlocked,
            "unlocked_at": record.get("unlocked_at"),
            "progress": list(progress) if progress else None,
            "status": STATUS[index.readiness[ach.id]],
        })
    done = sum(1 for item in items if item["unlocked"])
    return {
        "version": VIEW_VERSION,
        "game": game_id,
        "name": definition.text(lang),
        "updated_at": _now(),
        "unlocked": done,
        "total": len(items),
        "xp": state.xp_for(game_id),
        "xp_total": sum(ach.xp for ach in index.achievements),
        "achievements": items,
    }


def profile_view(state: UserState, games: list[dict[str, Any]]) -> dict[str, Any]:
    xp = state.xp_for()
    level = level_for_xp(xp)
    summary = [
        {"id": g["game"], "name": g["name"], "unlocked": g["unlocked"], "total": g["total"], "xp": g["xp"]}
        for g in games
    ]
    summary.sort(key=lambda g: (-g["unlocked"], g["name"].lower()))
    return {
        "version": VIEW_VERSION,
        "updated_at": _now(),
        "xp": xp,
        "level": level,
        "next_level_xp": xp_for_level(level + 1),
        "unlocked": sum(g["unlocked"] for g in summary),
        "total": sum(g["total"] for g in summary),
        "games": summary,
    }
