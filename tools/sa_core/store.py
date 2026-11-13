"""Estado do usuário e cálculo de XP/nível para a ferramenta de PC.

No console, a persistência usa journal + snapshot A/B (ver
docs/estudo-viabilidade.md, seção 8). Aqui basta um JSON com escrita atômica.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def level_for_xp(xp: int) -> int:
    level = 0
    while 100 * (level + 1) ** 1.5 <= xp:
        level += 1
    return level


def xp_for_level(level: int) -> int:
    return int(100 * level ** 1.5)


@dataclass
class UserState:
    unlocked: dict[str, dict[str, Any]] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    def is_unlocked(self, game_id: str, ach_id: str) -> bool:
        return f"{game_id}/{ach_id}" in self.unlocked

    def unlock(self, game_id: str, ach_id: str, xp: int, when: datetime | None = None) -> dict[str, Any]:
        stamp = (when or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        record = {"game": game_id, "achievement": ach_id, "xp": xp, "unlocked_at": stamp}
        self.unlocked[f"{game_id}/{ach_id}"] = record
        self.history.append(record)
        return record

    @property
    def total_xp(self) -> int:
        return sum(int(r["xp"]) for r in self.unlocked.values())

    def to_json(self) -> dict[str, Any]:
        return {"version": 1, "unlocked": self.unlocked, "history": self.history}

    @classmethod
    def from_json(cls, raw: dict[str, Any]) -> "UserState":
        return cls(unlocked=dict(raw.get("unlocked", {})), history=list(raw.get("history", [])))


def load_state(path: Path) -> UserState:
    if not path.exists():
        return UserState()
    with path.open(encoding="utf-8") as handle:
        return UserState.from_json(json.load(handle))


def save_state(state: UserState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(state.to_json(), handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
