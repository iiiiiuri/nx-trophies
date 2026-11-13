"""Contrato da estrutura padrão: todo games/*.json novo é testado aqui sem precisar de teste próprio."""

import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from _path import REPO_DIR, ensure_path

ensure_path()

import sa  # noqa: E402
from sa_core.catalog import (  # noqa: E402
    GAMES_DIR, check_definition, game_files, load_catalog, new_definition, resolve_game_path,
)
from sa_core.definition import DefinitionError, parse_definition  # noqa: E402

try:
    import jsonschema
except ImportError:
    jsonschema = None

SCHEMA_PATH = REPO_DIR / "schema" / "game-definition.schema.json"


def write(directory: Path, name: str, raw: dict) -> Path:
    path = directory / name
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


class RepositoryGamesTest(unittest.TestCase):
    def test_every_game_file_is_valid(self):
        files = game_files()
        self.assertTrue(files)
        catalog = load_catalog()
        self.assertEqual([str(p) for p in catalog.problems], [])
        self.assertEqual(set(catalog.games), {p.stem for p in files})

    def test_every_game_file_declares_the_schema(self):
        for path in game_files():
            with self.subTest(game=path.stem):
                raw = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(raw.get("$schema"), "../schema/game-definition.schema.json")

    def test_games_directory_is_flat(self):
        self.assertEqual([p.name for p in GAMES_DIR.iterdir() if p.is_dir()], [])

    @unittest.skipIf(jsonschema is None, "jsonschema não instalado")
    def test_every_game_file_matches_json_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        jsonschema.Draft7Validator.check_schema(schema)
        validator = jsonschema.Draft7Validator(schema)
        for path in game_files():
            with self.subTest(game=path.stem):
                errors = [e.message for e in validator.iter_errors(json.loads(path.read_text(encoding="utf-8")))]
                self.assertEqual(errors, [])


class StrictStructureTest(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads((GAMES_DIR / "mario_kart_8_deluxe.json").read_text(encoding="utf-8"))

    def broken(self, mutate):
        raw = copy.deepcopy(self.raw)
        mutate(raw)
        with self.assertRaises(DefinitionError) as ctx:
            parse_definition(raw)
        return str(ctx.exception)

    def test_typos_are_rejected(self):
        def typo(raw):
            raw["achievements"][0]["condtion"] = raw["achievements"][0].pop("condition")
        self.assertIn("condtion", self.broken(typo))
        self.assertIn("titleids", self.broken(lambda r: r["game"].update(titleids=[])))
        self.assertIn("ofset", self.broken(lambda r: r["bindings"][0]["variables"]["p1.star_timer"].update(ofset=1)))
        self.assertIn("extra", self.broken(lambda r: r.update(extra=1)))

    def test_identifiers(self):
        self.broken(lambda r: r["game"].update(id="Mario Kart"))
        self.broken(lambda r: r["game"].update(title_ids=["0100"]))
        self.broken(lambda r: r["game"].update(kind="pirata"))
        self.broken(lambda r: r["game"].pop("title_ids"))
        self.broken(lambda r: r["bindings"][0]["match"].update(build_ids=["XYZ"]))
        self.broken(lambda r: r["bindings"][0]["match"].update(build_ids=[]))
        self.broken(lambda r: r["events"].append(copy.deepcopy(r["events"][0])))
        self.broken(lambda r: r["achievements"][0].update(modes=["hard"]))
        self.broken(lambda r: r["achievements"][0].update(where_has="bit"))


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_problems_are_reported_per_file(self):
        write(self.dir, "good.json", new_definition("good", "Good", title_id="0100000000000001"))
        write(self.dir, "wrong_name.json", new_definition("other", "Other", title_id="0100000000000002"))
        write(self.dir, "clash.json", new_definition("clash", "Clash", title_id="0100000000000001"))
        (self.dir / "broken.json").write_text('{"schema_version": 2,\n  oops}', encoding="utf-8")
        catalog = load_catalog(self.dir)
        self.assertEqual(set(catalog.games), {"clash"})
        messages = {p.path.name: p.message for p in catalog.problems}
        self.assertIn("other.json", messages["wrong_name.json"])
        self.assertIn("linha 2", messages["broken.json"])
        self.assertIn("já pertence a clash", messages["good.json"])

    def test_detect(self):
        catalog = load_catalog()
        definition, binding = catalog.detect("01006bb00c6f0000", "ae16f71e002af8cb")
        self.assertEqual((definition.game_id, binding.id), ("zelda_links_awakening", "v1_0_x"))
        self.assertEqual(catalog.detect("0100152000022000", "1111111111111111")[1], None)
        self.assertEqual(catalog.detect("0100000000000000", "1111111111111111"), (None, None))

    def test_skeletons_are_valid(self):
        for raw in (new_definition("memory_game", "Memory", title_id="0100000000000003", build_id="ABCDEF0123456789"),
                    new_definition("save_game", "Save", save_file="Save/file1.sav")):
            with self.subTest(game=raw["game"]["id"]):
                path = write(self.dir, f"{raw['game']['id']}.json", raw)
                self.assertEqual(check_definition(path)[1], [])
                if jsonschema is not None:
                    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
                    self.assertEqual([e.message for e in jsonschema.Draft7Validator(schema).iter_errors(raw)], [])

    def test_resolve_game_path(self):
        self.assertEqual(resolve_game_path("mario_kart_8_deluxe"), GAMES_DIR / "mario_kart_8_deluxe.json")
        self.assertEqual(resolve_game_path("x/y.json"), Path("x/y.json"))


class CliCatalogTest(unittest.TestCase):
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = sa.main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()

    def test_validate_and_list(self):
        code, out, _ = self.run_cli("validate")
        self.assertEqual(code, 0)
        self.assertIn("0 problema(s)", out)
        code, out, _ = self.run_cli("list")
        self.assertEqual(code, 0)
        for game in ("mario_kart_8_deluxe", "zelda_links_awakening", "ship_of_harkinian"):
            self.assertIn(game, out)

    def test_new_then_validate(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(sa, "GAMES_DIR", Path(tmp)):
            code, out, _ = self.run_cli("new", "super_mario_odyssey", "--name", "Super Mario Odyssey",
                                        "--title-id", "0100000000010000", "--build-id", "0123456789ABCDEF")
            self.assertEqual(code, 0, out)
            path = Path(tmp) / "super_mario_odyssey.json"
            self.assertEqual(check_definition(path)[1], [])
            code, _, err = self.run_cli("new", "super_mario_odyssey", "--name", "x")
            self.assertEqual(code, 2)
            self.assertIn("já existe", err)

    def test_index_by_game_id(self):
        code, out, _ = self.run_cli("index", "zelda_links_awakening")
        self.assertEqual(code, 0)
        self.assertIn("plano de leitura", out)


if __name__ == "__main__":
    unittest.main()
