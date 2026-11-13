"""Motor de conquistas: aplica snapshots de variáveis sobre o índice.

Um tick: para cada instância (a memória do jogo, ou cada slot de save),
verifica `active_when`, detecta bordas de eventos e atualiza contadores,
e avalia as conquistas ainda bloqueadas conforme a prontidão:
LIVE desbloqueia, REHEARSAL só registra, PENDING/UNSUPPORTED é ignorada.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .definition import Achievement, Index, Readiness
from .expr import MISSING, Context, eval_condition, eval_value, parse_int
from .sources import Snapshot
from .store import UserState


@dataclass
class TickResult:
    unlocked: list[Achievement] = field(default_factory=list)
    rehearsal: list[Achievement] = field(default_factory=list)
    events: dict[str, int] = field(default_factory=dict)


class Engine:
    def __init__(self, index: Index, state: UserState):
        self.index = index
        self.state = state
        self.game_id = index.definition.game_id
        self._previous_events: dict[tuple[str, str], bool] = {}
        self._streaks: dict[str, int] = {}
        self._rehearsed: set[str] = set()

    def counters(self) -> dict[str, int]:
        return self.state.counters_for(self.game_id)

    def mode_of(self, snapshot: Snapshot) -> str:
        ctx = Context(snapshot.values, self.counters())
        for mode, cond in self.index.binding.instance_modes.items():
            if eval_condition(cond, ctx):
                return mode
        return "default"

    def _active(self, snapshot: Snapshot) -> bool:
        guard = self.index.binding.active_when
        return guard is None or eval_condition(guard, Context(snapshot.values, self.counters()))

    def tick(self, snapshots: list[Snapshot]) -> TickResult:
        result = TickResult()
        active = [s for s in snapshots if self._active(s)]
        counters = self.counters()

        for snapshot in active:
            ctx = Context(snapshot.values, counters)
            for event in self.index.events.values():
                key = (snapshot.label, event.id)
                now = eval_condition(event.when, ctx)
                if now and not self._previous_events.get(key, False):
                    counters[event.id] = counters.get(event.id, 0) + 1
                    result.events[event.id] = result.events.get(event.id, 0) + 1
                self._previous_events[key] = now

        for ach in self.index.achievements:
            readiness = self.index.readiness[ach.id]
            if readiness < Readiness.REHEARSAL or self.state.is_unlocked(self.game_id, ach.id):
                continue
            satisfied = any(
                (ach.modes is None or self.mode_of(s) in ach.modes)
                and eval_condition(ach.condition, Context(s.values, counters))
                for s in active
            )
            self._streaks[ach.id] = self._streaks.get(ach.id, 0) + 1 if satisfied else 0
            if self._streaks[ach.id] < ach.confirm_ticks:
                continue
            if readiness is Readiness.LIVE:
                self.state.unlock(self.game_id, ach.id, ach.xp)
                result.unlocked.append(ach)
            elif ach.id not in self._rehearsed:
                self._rehearsed.add(ach.id)
                result.rehearsal.append(ach)
        return result

    def progress(self, ach: Achievement, snapshots: list[Snapshot]) -> tuple[int, int] | None:
        if ach.progress is None:
            return None
        target = parse_int(ach.progress["target"])
        if self.state.is_unlocked(self.game_id, ach.id):
            return (target, target)
        best = None
        for snapshot in snapshots or [Snapshot("offline", {})]:
            if ach.modes is not None and self.mode_of(snapshot) not in ach.modes:
                continue
            value = eval_value(ach.progress["value"], Context(snapshot.values, self.counters()))
            if value is not MISSING:
                best = max(best or 0, min(int(value), target))
        return None if best is None else (best, target)
