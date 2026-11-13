"""O motor C++ (native/common) precisa dar o mesmo resultado do avaliador Python.

Compila native/tests/sa_host.cpp com o g++ do PC e roda os mesmos traces e
saves pelos dois lados. Sem g++, os testes são pulados.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _path import ensure_path

ensure_path()

from sa_core.catalog import load_catalog  # noqa: E402
from sa_core.definition import build_index  # noqa: E402
from sa_core.engine import Engine  # noqa: E402
from sa_core.layout import REPO_DIR  # noqa: E402
from sa_core.pack import compile_pack, pack_bytes  # noqa: E402
from sa_core.progress import game_view  # noqa: E402
from sa_core.expr import parse_int  # noqa: E402
from sa_core.sources import FakeProcess, FileSource, MemorySource  # noqa: E402
from sa_core.store import UserState  # noqa: E402

from soh_fixtures import early_game, late_game, make_save  # noqa: E402

NATIVE = REPO_DIR / "native"
TRACES = REPO_DIR / "examples" / "traces"
GXX = shutil.which("g++")


def apply_writes(process, writes):
    for write in writes:
        value = write["value"]
        process.write_value(process.address(write["addr"]), write["type"],
                            parse_int(value) if isinstance(value, str) else value)


@unittest.skipUnless(GXX, "g++ não encontrado")
class NativeParityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls.tmp.name)
        cls.binary = cls.dir / "sa_host"
        sources = sorted(str(p) for p in (NATIVE / "common" / "sa").glob("*.cpp"))
        objects = []
        cjson = cls.dir / "cJSON.o"
        subprocess.run(["gcc", "-c", "-O1", str(NATIVE / "common" / "third_party" / "cJSON.c"), "-o", str(cjson)],
                       check=True)
        objects.append(str(cjson))
        subprocess.run([GXX, "-std=c++17", "-O1", "-Wall", "-Werror", f"-I{NATIVE / 'common'}",
                        f"-I{NATIVE / 'common' / 'third_party'}", *sources, str(NATIVE / "tests" / "sa_host.cpp"),
                        *objects, "-o", str(cls.binary)], check=True)
        cls.catalog = load_catalog()
        cls.packs = {}
        for game_id, definition in cls.catalog.games.items():
            path = cls.dir / f"{game_id}.json"
            path.write_bytes(pack_bytes(compile_pack(definition)))
            cls.packs[game_id] = path

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def native(self, *args):
        out = subprocess.run([str(self.binary), *map(str, args)], check=True, capture_output=True, text=True).stdout
        return [json.loads(line) for line in out.splitlines() if line.strip()]

    def python_trace(self, game_id, trace_path):
        definition = self.catalog.games[game_id]
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        binding = definition.binding_for_build(trace["build_id"])
        index = build_index(definition, binding)
        process = FakeProcess({name: (parse_int(r["base"]), parse_int(r["size"]))
                               for name, r in trace["regions"].items()})
        apply_writes(process, trace.get("initial", []))
        engine = Engine(index, UserState())
        source = MemorySource(index, process)
        ticks = []
        for tick in trace["ticks"]:
            apply_writes(process, tick.get("writes", []))
            result = engine.tick(source.read())
            ticks.append({"unlocked": [a.id for a in result.unlocked],
                          "rehearsal": [a.id for a in result.rehearsal],
                          "events": result.events})
        return ticks

    def test_memory_traces_match(self):
        for game_id, trace in (("mario_kart_8_deluxe", "mk8_corrida.json"),
                               ("zelda_links_awakening", "la_progresso.json")):
            with self.subTest(game=game_id):
                expected = self.python_trace(game_id, TRACES / trace)
                got = self.native("trace", self.packs[game_id], TRACES / trace)
                self.assertEqual(got, expected)
                self.assertTrue(any(t["unlocked"] for t in expected), "trace sem desbloqueio não testa nada")

    def soh_files(self):
        saves = [early_game(), late_game(), make_save(gs_tokens=100, deaths=0, randomizer=True),
                 make_save(master_quest=True, quest_items=0x3F)]
        paths = []
        for number, save in enumerate(saves, start=1):
            path = self.dir / f"file{number}.sav"
            path.write_text(json.dumps(save, indent=2), encoding="utf-8")
            paths.append(path)
        paths += sorted((REPO_DIR / "examples" / "soh" / "Save").glob("*.sav"))
        return paths

    def test_soh_saves_match(self):
        definition = self.catalog.games["ship_of_harkinian"]
        index = build_index(definition, next(iter(definition.bindings.values())))
        for path in self.soh_files():
            with self.subTest(save=path.name):
                result = Engine(index, UserState()).tick(FileSource(index, [path]).read())
                got = self.native("saves", self.packs["ship_of_harkinian"], path)[0]
                self.assertEqual(sorted(got["unlocked"]), sorted(a.id for a in result.unlocked))
                self.assertEqual(sorted(got["rehearsal"]), sorted(a.id for a in result.rehearsal))

    def test_soh_view_matches(self):
        definition = self.catalog.games["ship_of_harkinian"]
        index = build_index(definition, next(iter(definition.bindings.values())))
        paths = self.soh_files()[:2]
        state = UserState()
        snapshots = FileSource(index, paths).read()
        Engine(index, state).tick(snapshots)
        expected = game_view(index, state, snapshots, "pt-BR")
        got = self.native("view", self.packs["ship_of_harkinian"], *paths)[0]
        for view in (expected, got):
            view.pop("updated_at")
            for item in view["achievements"]:
                item.pop("unlocked_at")
        self.assertEqual(got, expected)

    def test_broken_save_is_ignored(self):
        path = self.dir / "quebrado.sav"
        text = json.dumps(late_game())
        path.write_text(text[:len(text) // 2], encoding="utf-8")
        got = self.native("saves", self.packs["ship_of_harkinian"], path)[0]
        self.assertEqual(got["unlocked"], [])
