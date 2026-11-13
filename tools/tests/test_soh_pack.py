import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from _path import REPO_DIR, ensure_path

ensure_path()

import sa_eval  # noqa: E402
from sa_core.pack import PackError, Slot, Status, evaluate, load_pack, parse_pack  # noqa: E402
from sa_core.store import level_for_xp  # noqa: E402
from soh_fixtures import early_game, late_game, make_save  # noqa: E402

PACK_PATH = REPO_DIR / "packs" / "ship_of_harkinian" / "pack.json"
PACK = load_pack(PACK_PATH)
SOURCE = PACK.sources["save"]


def statuses(*docs):
    slots = [Slot(f"file{i + 1}.sav", d) for i, d in enumerate(docs)]
    return {a.id: evaluate(a, SOURCE, slots) for a in PACK.achievements}


def unlocked(*docs):
    return {k for k, r in statuses(*docs).items() if r.status is Status.UNLOCKED}


class SohPackTest(unittest.TestCase):
    def test_fresh_save_unlocks_nothing(self):
        self.assertEqual(unlocked(make_save()), set())

    def test_early_game(self):
        self.assertEqual(
            unlocked(early_game()),
            {"kokiri_sword", "fairy_ocarina", "defeat_gohma", "first_death", "speedy_gohma"},
        )

    def test_late_game(self):
        got = unlocked(late_game())
        for ach_id in ("six_medallions", "spiritual_stones", "all_songs", "hero_of_time", "deathless",
                       "master_sword", "biggoron_sword", "ten_hours", "enemies_500", "rolls_1000", "dark_link"):
            self.assertIn(ach_id, got)
        for ach_id in ("skulltulas_100", "twenty_hearts", "pots_300", "first_death", "speedy_gohma"):
            self.assertNotIn(ach_id, got)

    def test_progress(self):
        result = statuses(late_game())
        self.assertEqual(result["skulltulas_100"].progress, (63, 100))
        self.assertEqual(result["twenty_hearts"].progress, (17, 20))
        self.assertEqual(result["six_medallions"].progress, (6, 6))
        self.assertEqual(statuses(early_game())["spiritual_stones"].progress, (1, 3))

    def test_slots_are_combined(self):
        got = unlocked(early_game(), late_game())
        self.assertIn("speedy_gohma", got)
        self.assertIn("deathless", got)

    def test_quest_bit_fallback_without_timestamps(self):
        self.assertIn("defeat_morpha", unlocked(make_save(quest_items=0x04)))

    def test_counts_guard_marks_unsupported(self):
        result = statuses(make_save(counts_len=90, counts={12: 1}))
        self.assertIs(result["dark_link"].status, Status.UNSUPPORTED)
        self.assertIs(result["rolls_1000"].status, Status.UNSUPPORTED)

    def test_randomizer_excludes_story(self):
        result = statuses(make_save(randomizer=True, quest_items=0x3F, equipment=0x1))
        self.assertIs(result["six_medallions"].status, Status.UNSUPPORTED)
        self.assertIs(result["kokiri_sword"].status, Status.UNLOCKED)

    def test_missing_sections_do_not_unlock(self):
        self.assertEqual(unlocked({"version": 1, "sections": {}}), set())
        self.assertEqual(unlocked({"garbage": True}), set())

    def test_secret_text_stays_hidden_until_unlocked(self):
        ach = PACK.by_id("deathless")
        self.assertTrue(ach.secret)


class PackValidationTest(unittest.TestCase):
    def raw(self):
        return json.loads(PACK_PATH.read_text(encoding="utf-8"))

    def test_duplicate_id(self):
        raw = self.raw()
        raw["achievements"].append(copy.deepcopy(raw["achievements"][0]))
        with self.assertRaises(PackError):
            parse_pack(raw)

    def test_unknown_operator(self):
        raw = self.raw()
        raw["achievements"][0]["condition"] = {"value": "base.deaths", "op": "~=", "rhs": 1}
        with self.assertRaises(PackError):
            parse_pack(raw)

    def test_bad_rarity_and_schema(self):
        raw = self.raw()
        raw["achievements"][0]["rarity"] = "mythic"
        with self.assertRaises(PackError):
            parse_pack(raw)
        raw = self.raw()
        raw["schema_version"] = 2
        with self.assertRaises(PackError):
            parse_pack(raw)


class CliTest(unittest.TestCase):
    def run_cli(self, *args):
        out = io.StringIO()
        with redirect_stdout(out):
            code = sa_eval.main([str(a) for a in args])
        return code, out.getvalue()

    def test_state_notifications_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            save = tmp / "Save" / "file1.sav"
            save.parent.mkdir()
            save.write_text(json.dumps(make_save(equipment=0x1)), encoding="utf-8")
            state, notify = tmp / "state.json", tmp / "notify"

            code, out = self.run_cli(PACK_PATH, "--save-dir", save.parent, "--state", state, "--notify-dir", notify)
            self.assertEqual(code, 0)
            self.assertIn("CONQUISTA DESBLOQUEADA: Pequeno Espadachim", out)
            files = list(notify.glob("SwitchAchievements-*.notify"))
            self.assertEqual(len(files), 1)
            payload = json.loads(files[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["title"], "Conquista desbloqueada")
            self.assertIn("+10 XP", payload["text"])

            save.write_text(json.dumps(early_game()), encoding="utf-8")
            _, out = self.run_cli(PACK_PATH, "--save-dir", save.parent, "--state", state, "--notify-dir", notify)
            self.assertNotIn("Pequeno Espadachim (+", out)
            self.assertEqual(len(list(notify.glob("*.notify"))), 5)

            saved = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(len(saved["history"]), 5)

            save.write_text(json.dumps(make_save()), encoding="utf-8")
            _, out = self.run_cli(PACK_PATH, "--save-dir", save.parent, "--state", state)
            self.assertIn(f"5/{len(PACK.achievements)} conquistas", out)

    def test_secret_hidden_in_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            save = Path(tmp) / "file1.sav"
            save.write_text(json.dumps(make_save()), encoding="utf-8")
            _, out = self.run_cli(PACK_PATH, "--save", save)
            self.assertNotIn("Imortal", out)
            self.assertIn("Conquista secreta", out)

    def test_corrupt_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            save = Path(tmp) / "file1.sav"
            save.write_text('{"version": 1, "sect', encoding="utf-8")
            code, _ = self.run_cli(PACK_PATH, "--save", save)
            self.assertEqual(code, 0)


class LevelTest(unittest.TestCase):
    def test_curve(self):
        self.assertEqual(level_for_xp(0), 0)
        self.assertEqual(level_for_xp(99), 0)
        self.assertEqual(level_for_xp(100), 1)
        self.assertEqual(level_for_xp(283), 2)


if __name__ == "__main__":
    unittest.main()
