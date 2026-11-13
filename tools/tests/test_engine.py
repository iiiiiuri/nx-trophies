import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _path import REPO_DIR, ensure_path

ensure_path()

import sa  # noqa: E402
import traces  # noqa: E402
from sa_core.definition import Readiness, build_index, load_definition  # noqa: E402
from sa_core.engine import Engine  # noqa: E402
from sa_core.expr import MISSING  # noqa: E402
from sa_core.sources import FakeProcess, MemorySource, snapshot_from_document  # noqa: E402
from sa_core.store import UserState, level_for_xp  # noqa: E402
from soh_fixtures import early_game, late_game, make_save  # noqa: E402

GAMES = REPO_DIR / "games"


def replay(game: str, trace: dict, state: UserState | None = None):
    definition = load_definition(GAMES / f"{game}.json")
    index = build_index(definition, definition.binding_for_build(trace["build_id"]))
    process = FakeProcess({k: (int(v["base"], 0), int(v["size"], 0)) for k, v in trace["regions"].items()})
    state = state or UserState()
    engine = Engine(index, state)
    source = MemorySource(index, process)
    log = []
    for tick in trace["ticks"]:
        sa.apply_writes(process, tick["writes"])
        result = engine.tick(source.read())
        log.append((tick["label"], [a.id for a in result.unlocked], [a.id for a in result.rehearsal]))
    return index, engine, state, source, log


class MemorySourceTest(unittest.TestCase):
    def test_chain_resolution_and_null_pointer(self):
        definition = load_definition(GAMES / "mario_kart_8_deluxe.json")
        index = build_index(definition, definition.binding_for_build("FE941ED5BA14BE5D"))
        process = FakeProcess({"main": (0x8000000, 0x2000000), "heap": (0x40000000, 0x10000000)})
        source = MemorySource(index, process)
        self.assertIs(source.read()[0].values["p1.star_timer"], MISSING)

        sa.apply_writes(process, [{"addr": "main+0x1354AF0", "type": "u64", "value": traces.KART_HOLDER},
                                  {"addr": hex(traces.KART_HOLDER + 0x6E0), "type": "u64", "value": traces.KART},
                                  {"addr": hex(traces.KART + 0x7BC), "type": "u32", "value": 447}])
        self.assertEqual(source.read()[0].values["p1.star_timer"], 447)

    def test_pointer_outside_regions_is_rejected(self):
        definition = load_definition(GAMES / "mario_kart_8_deluxe.json")
        index = build_index(definition, definition.binding_for_build("FE941ED5BA14BE5D"))
        process = FakeProcess({"main": (0x8000000, 0x2000000), "heap": (0x40000000, 0x10000000)})
        sa.apply_writes(process, [{"addr": "main+0x1354AF0", "type": "u64", "value": 0xDEAD0000}])
        self.assertIs(MemorySource(index, process).read()[0].values["p1.star_timer"], MISSING)


class Mk8Test(unittest.TestCase):
    def setUp(self):
        self.index, self.engine, self.state, self.source, self.log = replay("mario_kart_8_deluxe", traces.mk8_race())

    def test_events_count_rising_edges_only_while_active(self):
        counters = self.state.counters_for("mario_kart_8_deluxe")
        self.assertEqual(counters["star_used"], 2)
        self.assertEqual(counters["shocked"], 1)
        self.assertEqual(counters["lakitu_rescue"], 1)
        self.assertEqual(counters["bullet_bill"], 1)
        self.assertNotIn("race_won", counters)

    def test_unlocks_and_rehearsal(self):
        unlocked = {a for _, u, _ in self.log for a in u}
        rehearsed = {a for _, _, r in self.log for a in r}
        self.assertEqual(unlocked, {"star_first"})
        self.assertEqual(rehearsed, {"bullet_bill_first"})
        self.assertEqual(self.log[2][1], ["star_first"])
        self.assertFalse(self.state.is_unlocked("mario_kart_8_deluxe", "bullet_bill_first"))

    def test_counters_persist_across_sessions(self):
        _, engine, state, _, _ = replay("mario_kart_8_deluxe", traces.mk8_race(), self.state)
        self.assertEqual(state.counters_for("mario_kart_8_deluxe")["star_used"], 4)
        self.assertEqual(engine.progress(self.index.by_id("star_50"), []), (4, 50))

    def test_one_block_per_tick(self):
        self.assertEqual(len(self.index.read_plan), 1)
        ticks = len(traces.mk8_race()["ticks"])
        self.assertLessEqual(self.source.read_calls, ticks * 3)


class LinksAwakeningTest(unittest.TestCase):
    def setUp(self):
        self.index, self.engine, self.state, _, self.log = replay("zelda_links_awakening", traces.la_progress())

    def test_unlocks(self):
        unlocked = {a for _, u, _ in self.log for a in u}
        self.assertTrue({"trade.dog_food", "trade.bananas", "figure.ciaociao", "figure.goomba", "figure.bow_wow",
                         "figures_5", "golden_leaves", "follower.marin", "rupees_999"} <= unlocked)
        self.assertNotIn("trade.yoshi_doll", unlocked)
        self.assertNotIn("trade_complete", unlocked)

    def test_assumed_values_only_rehearse(self):
        rehearsed = {a for _, _, r in self.log for a in r}
        self.assertEqual(rehearsed, {"trade.yoshi_doll", "trade.ribbon", "dungeon_treasures.tail_cave"})

    def test_pending_never_evaluated(self):
        self.assertIs(self.index.readiness["all_instruments"], Readiness.PENDING)


class SohTest(unittest.TestCase):
    def setUp(self):
        definition = load_definition(GAMES / "ship_of_harkinian.json")
        self.index = build_index(definition, definition.bindings["soh_save_json"])

    def unlocked(self, *docs):
        state = UserState()
        engine = Engine(self.index, state)
        engine.tick([snapshot_from_document(self.index, f"file{i}.sav", d) for i, d in enumerate(docs)])
        return {k.split("/", 1)[1] for k in state.unlocked}

    def test_fresh_save(self):
        self.assertEqual(self.unlocked(make_save()), set())

    def test_early_game(self):
        self.assertEqual(self.unlocked(early_game()),
                         {"sword.kokiri", "boss.gohma", "song.lullaby", "song.saria", "speedy_gohma"})

    def test_late_game(self):
        got = self.unlocked(late_game())
        for ach in ("six_medallions", "spiritual_stones", "all_songs", "hero_of_time", "deathless",
                    "sword.master", "sword.biggoron", "ten_hours", "stat_rolls", "stat_dark_link", "boss.twinrova"):
            self.assertIn(ach, got)
        for ach in ("skulltulas_100", "twenty_hearts", "speedy_gohma"):
            self.assertNotIn(ach, got)

    def test_slots_combine_and_modes(self):
        self.assertIn("speedy_gohma", self.unlocked(early_game(), late_game()))
        rando = self.unlocked(make_save(randomizer=True, quest_items=0x3F, equipment=0x1))
        self.assertIn("sword.kokiri", rando)
        self.assertNotIn("six_medallions", rando)

    def test_stat_table_guard(self):
        self.assertNotIn("stat_dark_link", self.unlocked(make_save(counts_len=90, counts={12: 1})))

    def test_garbage_document(self):
        self.assertEqual(self.unlocked({"garbage": True}), set())


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = sa.main([str(a) for a in args])
        return code, out.getvalue()

    def test_index(self):
        code, out = self.run_cli("index", GAMES / "mario_kart_8_deluxe.json")
        self.assertEqual(code, 0)
        self.assertIn("[[main+0x1354AF0]+0x6E0]", out)
        self.assertIn("gold_150.spiny", out)

    def test_replay_with_notifications_and_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            trace = tmp / "race.json"
            trace.write_text(json.dumps(traces.mk8_race()), encoding="utf-8")
            code, out = self.run_cli("replay", GAMES / "mario_kart_8_deluxe.json", trace,
                                     "--state", tmp / "state.json", "--notify-dir", tmp / "notify")
            self.assertEqual(code, 0)
            self.assertIn("CONQUISTA DESBLOQUEADA: Brilho de Estrela", out)
            self.assertIn("ensaio: 'Bala Humana'", out)
            self.assertEqual(len(list((tmp / "notify").glob("SwitchAchievements-*.notify"))), 1)
            saved = json.loads((tmp / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["counters"]["mario_kart_8_deluxe"]["star_used"], 2)

    def test_unknown_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            trace = Path(tmp) / "t.json"
            data = traces.mk8_race()
            data["build_id"] = "0123456789ABCDEF"
            trace.write_text(json.dumps(data), encoding="utf-8")
            code, _ = self.run_cli("replay", GAMES / "mario_kart_8_deluxe.json", trace)
            self.assertEqual(code, 2)

    def test_save_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_dir = Path(tmp) / "Save"
            save_dir.mkdir()
            (save_dir / "file1.sav").write_text(json.dumps(early_game()), encoding="utf-8")
            code, out = self.run_cli("save", GAMES / "ship_of_harkinian.json", "--save-dir", save_dir)
            self.assertEqual(code, 0)
            self.assertIn("CONQUISTA DESBLOQUEADA: Espada Kokiri", out)
            self.assertNotIn("Imortal", out)


class LevelTest(unittest.TestCase):
    def test_curve(self):
        self.assertEqual([level_for_xp(x) for x in (0, 99, 100, 283)], [0, 0, 1, 2])


if __name__ == "__main__":
    unittest.main()
