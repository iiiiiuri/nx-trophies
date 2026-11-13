import copy
import json
import unittest

from _path import REPO_DIR, ensure_path

ensure_path()

from sa_core.definition import (  # noqa: E402
    Confidence, DefinitionError, Readiness, build_index, load_definition, parse_definition,
)

GAMES = REPO_DIR / "games"
DEFINITIONS = sorted(GAMES.glob("*.json"))

MINIMAL = {
    "schema_version": 2,
    "game": {"id": "toy", "name": "Toy", "title_ids": ["0100000000001000"]},
    "content": {
        "gems": [
            {"id": "red", "name": {"en": "Red", "pt-BR": "Vermelha"}, "bit": 0, "slot": 0},
            {"id": "blue", "name": {"en": "Blue", "pt-BR": "Azul"}, "bit": 1, "slot": 1, "confidence": "assumed"},
            {"id": "green", "name": {"en": "Green", "pt-BR": "Verde"}, "bit": 2},
        ]
    },
    "variables": {
        "gems": {"type": "u8"},
        "gem.count": {"type": "u16", "indexed_by": "gems"},
        "unknown": {"type": "u8"},
    },
    "bindings": [{
        "id": "b1", "source": "memory", "match": {"build_ids": ["AAAAAAAAAAAAAAAA"]},
        "pointers": {"obj": {"base": "heap", "chain": ["0x10", "0x8"]}},
        "variables": {
            "gems": {"base": "main", "offset": "0x100", "confidence": "verified"},
            "gem.count": {"from": "obj", "offset": "0x20", "stride": "0x4", "index_key": "slot", "confidence": "community"},
            "unknown": {"confidence": "to_discover"},
        },
    }],
    "events": [],
    "achievements": [
        {"id": "gem", "for_each": "gems", "name": {"pt-BR": "Gema {item.name}", "en": "{item.name} gem"},
         "description": "d", "condition": {"value": "gems", "op": "has_all", "rhs": "{item.mask}"}},
        {"id": "all", "name": "All", "description": "d",
         "condition": {"value": "gems", "op": "has_all", "rhs": {"content_mask": {"of": "gems"}}}},
        {"id": "counts", "name": "Counts", "description": "d",
         "progress": {"value": {"count_of": "gems", "condition": {"value": "gem.count[{each.id}]", "op": ">", "rhs": 0}}, "target": 3},
         "condition": {"for_all": "gems", "condition": {"value": "gem.count[{each.id}]", "op": ">", "rhs": 0}}},
        {"id": "mystery", "name": "M", "description": "d", "condition": {"value": "unknown", "op": "==", "rhs": 1}},
        {"id": "nobind", "name": "N", "description": "d", "condition": {"value": "gems.extra", "op": "==", "rhs": 1}},
    ],
}


def toy(mutate=None):
    raw = copy.deepcopy(MINIMAL)
    if mutate:
        mutate(raw)
    return parse_definition(raw)


class ShippedDefinitionsTest(unittest.TestCase):
    def test_all_definitions_load_and_index(self):
        self.assertLessEqual({"mario_kart_8_deluxe", "zelda_links_awakening", "ship_of_harkinian"},
                             {p.stem for p in DEFINITIONS})
        for path in DEFINITIONS:
            with self.subTest(game=path.stem):
                definition = load_definition(path)
                for binding in definition.bindings.values():
                    index = build_index(definition, binding)
                    self.assertTrue(index.achievements)
                    self.assertEqual(set(index.readiness), {a.id for a in index.achievements})

    def test_build_lookup_is_case_insensitive(self):
        definition = load_definition(GAMES / "zelda_links_awakening.json")
        self.assertIsNotNone(definition.binding_for_build("ae16f71e002af8cb"))
        self.assertIsNone(definition.binding_for_build("0000000000000000"))


class TemplateTest(unittest.TestCase):
    def test_for_each_expansion(self):
        d = toy()
        gems = [a for a in d.achievements if a.template == "gem"]
        self.assertEqual([a.id for a in gems], ["gem.red", "gem.blue", "gem.green"])
        self.assertEqual(gems[1].name["pt-BR"], "Gema Azul")
        self.assertEqual(gems[1].condition["rhs"], 2)

    def test_content_mask_and_aggregates(self):
        d = toy()
        ach = {a.id: a for a in d.achievements}
        self.assertEqual(ach["all"].condition["rhs"], 0b111)
        self.assertEqual(len(ach["counts"].condition["all"]), 3)
        self.assertEqual(ach["counts"].condition["all"][2]["value"], "gem.count[green]")
        self.assertIn("sum", ach["counts"].progress["value"])

    def test_missing_placeholder_key(self):
        def mutate(raw):
            raw["achievements"][0]["condition"]["rhs"] = "{item.nope}"
        with self.assertRaises(DefinitionError):
            toy(mutate)


class IndexTest(unittest.TestCase):
    def setUp(self):
        d = toy()
        self.index = build_index(d, d.bindings["b1"])

    def test_indexed_instances(self):
        inst = self.index.instances
        self.assertEqual(inst["gem.count[red]"].offset, 0x20)
        self.assertEqual(inst["gem.count[blue]"].offset, 0x24)
        self.assertIs(inst["gem.count[blue]"].confidence, Confidence.ASSUMED)
        self.assertIs(inst["gem.count[green]"].confidence, Confidence.TO_DISCOVER)

    def test_readiness(self):
        r = self.index.readiness
        self.assertIs(r["gem.red"], Readiness.LIVE)
        self.assertIs(r["gem.blue"], Readiness.REHEARSAL)
        self.assertIs(r["all"], Readiness.REHEARSAL)
        self.assertIs(r["counts"], Readiness.PENDING)
        self.assertIs(r["mystery"], Readiness.PENDING)
        self.assertIs(r["nobind"], Readiness.UNSUPPORTED)

    def test_read_plan_groups_by_anchor(self):
        plan = {(b.anchor, b.offset, b.size) for b in self.index.read_plan}
        self.assertEqual(plan, {("ptr:obj", 0x20, 6), ("region:main", 0x100, 1)})

    def test_la_plan_is_two_blocks(self):
        d = load_definition(GAMES / "zelda_links_awakening.json")
        index = build_index(d, d.binding_for_build("909E904AF78AC1B8"))
        self.assertEqual(len(index.read_plan), 2)
        self.assertEqual(index.instances["dungeon.treasures[angler_tunnel]"].offset, 0x1CBB331)


class ValidationTest(unittest.TestCase):
    def check(self, mutate):
        with self.assertRaises(DefinitionError):
            toy(mutate)

    def test_errors(self):
        self.check(lambda r: r.update(schema_version=1))
        self.check(lambda r: r["achievements"].append(copy.deepcopy(r["achievements"][1])))
        self.check(lambda r: r["achievements"][1].update(rarity="mythic"))
        self.check(lambda r: r["achievements"][1].update(condition={"value": "gems", "op": "~=", "rhs": 1}))
        self.check(lambda r: r["variables"]["gems"].update(type="u128"))
        self.check(lambda r: r["bindings"][0]["variables"].update(ghost={"confidence": "verified"}))
        self.check(lambda r: r["bindings"][0]["pointers"]["obj"].update(base="stack"))
        self.check(lambda r: r["bindings"][0]["pointers"]["obj"].update(chain=[]))
        self.check(lambda r: r["bindings"][0]["variables"]["gems"].update(confidence="maybe"))
        self.check(lambda r: r["achievements"][1].update(condition={"value": {"count": "nope"}, "op": ">", "rhs": 0}))

    def test_memory_binding_requires_location(self):
        d = toy(lambda r: r["bindings"][0]["variables"]["gems"].pop("base"))
        with self.assertRaises(DefinitionError):
            build_index(d, d.bindings["b1"])

    def test_definitions_are_plain_json(self):
        for path in DEFINITIONS:
            json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
