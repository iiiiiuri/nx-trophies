"""Ícones, som, visão da tela do console e espelho do SD."""

import json
import struct
import tempfile
import unittest
import wave
import zlib
from pathlib import Path

from _path import ensure_path

ensure_path()

from sa_core.assets import AssetError, check_wav, icon_key, icon_keys, shown_icon_key  # noqa: E402
from sa_core.catalog import load_catalog  # noqa: E402
from sa_core.definition import build_index  # noqa: E402
from sa_core.images import png_to_rgba, read_png  # noqa: E402
from sa_core.layout import (  # noqa: E402
    ICONS_DIR, SD_OVERLAY, SD_VERSION, SD_SOUND, SOUND_FILE, UH_SOUND, icon_file, icon_png_file, pack_file, ultrahand_app_name,
    ultrahand_icon_file,
)
from sa_core.notify import notification_name  # noqa: E402
from sa_core.progress import game_view, profile_view  # noqa: E402
from sa_core.sdcard import build_sd  # noqa: E402
from sa_core.sources import FileSource  # noqa: E402
from sa_core.store import UserState  # noqa: E402

from soh_fixtures import make_save  # noqa: E402


def write_png(path: Path, width: int, height: int, rgba: bytes) -> None:
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    rows = b"".join(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")
    path.write_bytes(data)


def soh():
    definition = load_catalog().games["ship_of_harkinian"]
    return build_index(definition, next(iter(definition.bindings.values())))


class ImageTest(unittest.TestCase):
    def test_png_roundtrip_and_resize(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "x.png"
            pixels = bytes([255, 0, 0, 255] * 4 + [0, 0, 255, 0] * 4)
            write_png(path, 4, 2, pixels)
            self.assertEqual(read_png(path), (4, 2, pixels))
            small = png_to_rgba(path, 1)
            self.assertEqual(len(small), 4)
            self.assertEqual(small[0], 255)
            self.assertEqual(small[3], 128)

    def test_repository_icons_decode_to_50x50(self):
        keys = icon_keys()
        self.assertIn("common/trophy", keys)
        self.assertIn("common/secret", keys)
        for key in keys:
            with self.subTest(icon=key):
                self.assertEqual(len(png_to_rgba(ICONS_DIR / f"{key}.png", 50)), 50 * 50 * 4)


class IconTest(unittest.TestCase):
    def test_icon_by_item_then_template_then_default(self):
        index = soh()
        boss = index.by_id("boss.gohma")
        self.assertEqual(icon_key("ship_of_harkinian", boss), "ship_of_harkinian/boss.gohma")
        self.assertEqual(icon_key("jogo_sem_icones", boss), "common/trophy")
        with tempfile.TemporaryDirectory() as raw:
            icons = Path(raw)
            (icons / "ship_of_harkinian").mkdir()
            self.assertEqual(icon_key("ship_of_harkinian", boss, icons), "common/trophy")
            (icons / "ship_of_harkinian" / "boss.png").write_bytes(b"")
            self.assertEqual(icon_key("ship_of_harkinian", boss, icons), "ship_of_harkinian/boss")
            (icons / "ship_of_harkinian" / "boss.gohma.png").write_bytes(b"")
            self.assertEqual(icon_key("ship_of_harkinian", boss, icons), "ship_of_harkinian/boss.gohma")

    def test_locked_secret_hides_icon(self):
        secret = next(a for a in soh().achievements if a.secret)
        self.assertEqual(shown_icon_key("ship_of_harkinian", secret, False), "common/secret")
        self.assertNotEqual(shown_icon_key("ship_of_harkinian", secret, True), "common/secret")

    def test_ultrahand_finds_icon_from_notify_name(self):
        name = notification_name("ship_of_harkinian/boss")
        base = name[:name.rfind(".")]
        base = base[:base.rfind("-")]
        self.assertEqual(base, ultrahand_app_name("ship_of_harkinian/boss"))
        self.assertEqual(name.split("-", 1)[0], "SwitchAchievements")
        self.assertTrue(ultrahand_icon_file("ship_of_harkinian/boss").endswith(f"{base}.rgba"))


class SoundTest(unittest.TestCase):
    def test_repository_sound_is_valid(self):
        self.assertEqual(check_wav(SOUND_FILE), (1, 48000))

    def test_rejects_unsupported_rate(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "x.wav"
            with wave.open(str(path), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(12345)
                w.writeframes(b"\x00\x00" * 10)
            with self.assertRaises(AssetError):
                check_wav(path)


class ViewTest(unittest.TestCase):
    def test_game_view_and_profile(self):
        index = soh()
        state = UserState()
        state.unlock("ship_of_harkinian", "boss.gohma", 50)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "file1.sav"
            path.write_text(json.dumps(make_save(gs_tokens=4)), encoding="utf-8")
            snapshots = FileSource(index, [path]).read()
        view = game_view(index, state, snapshots, "pt-BR")
        self.assertEqual((view["unlocked"], view["total"], view["xp"]), (1, len(index.achievements), 50))
        items = {item["id"]: item for item in view["achievements"]}
        self.assertTrue(items["boss.gohma"]["unlocked"])
        self.assertEqual(items["boss.gohma"]["icon"], "ship_of_harkinian/boss.gohma")
        self.assertEqual(items["skulltulas_100"]["progress"], [4, 100])
        secret = next(item for item in view["achievements"] if item["secret"])
        self.assertEqual((secret["name"], secret["icon"]), ("Conquista secreta", "common/secret"))
        profile = profile_view(state, [view])
        self.assertEqual((profile["xp"], profile["unlocked"], profile["games"][0]["id"]),
                         (50, 1, "ship_of_harkinian"))


class SdBuildTest(unittest.TestCase):
    def test_build_lays_out_the_card(self):
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw) / "sd"
            missing = Path(raw) / "ausente"
            result = build_sd(root, overlay=missing, sysmodule=missing, app=missing)
            files = set(result.files)
            self.assertIn(icon_file("common/trophy"), files)
            self.assertIn(ultrahand_icon_file("ship_of_harkinian/boss"), files)
            self.assertIn(pack_file("ship_of_harkinian"), files)
            self.assertIn(icon_png_file("common/trophy"), files)
            self.assertIn(SD_VERSION, files)
            self.assertIn(SD_SOUND, files)
            self.assertIn(UH_SOUND, files)
            self.assertNotIn(SD_OVERLAY, files)
            self.assertFalse(any("state.json" in f or "progress/" in f for f in files))
            self.assertEqual((root / icon_file("common/trophy")).stat().st_size, 50 * 50 * 4)
            quiet = build_sd(root, overlay=missing, sysmodule=missing, app=missing, with_sound=False)
            self.assertNotIn(UH_SOUND, quiet.files)
