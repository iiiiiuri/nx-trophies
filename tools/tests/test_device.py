"""FTP local: raiz do SD, leitura e escrita com criação de pastas, sem rede."""

import json
import tempfile
import unittest
from ftplib import error_perm
from pathlib import Path

from _path import ensure_path

ensure_path()

from sa_core.device import (  # noqa: E402
    DeviceError, FtpDevice, load_endpoint, require_private_host, sd_mounts,
)
from sa_core.layout import SOH_SAVE, UH_NOTIFICATIONS  # noqa: E402
from sa_core.notify import test_notification  # noqa: E402


class FakeFtp:
    def __init__(self, tree: dict) -> None:
        self.tree = tree
        self.cwd_path = "/"
        self.quit_called = False

    def pwd(self) -> str:
        return self.cwd_path

    def cwd(self, name: str) -> None:
        if name == "/":
            self.cwd_path = "/"
            return
        target = name.rstrip("/") if name.startswith("/") else _join(self.cwd_path, name)
        if not isinstance(self._node(target), dict):
            raise error_perm(f"550 {name}: not a directory")
        self.cwd_path = target

    def mkd(self, name: str) -> None:
        node = self._node(self.cwd_path)
        node.setdefault(name, {})

    def nlst(self) -> list[str]:
        node = self._node(self.cwd_path)
        if not isinstance(node, dict) or not node:
            raise error_perm("550 No files found")
        return list(node)

    def retrbinary(self, cmd: str, callback) -> None:
        name = cmd.split(" ", 1)[1]
        data = self._node(self.cwd_path)[name]
        if not isinstance(data, bytes):
            raise error_perm(f"550 {name}")
        callback(data)

    def storbinary(self, cmd: str, handle) -> None:
        name = cmd.split(" ", 1)[1]
        self._node(self.cwd_path)[name] = handle.read()

    def quit(self) -> None:
        self.quit_called = True

    def _node(self, path: str):
        node = self.tree
        if path == "/":
            return node
        for part in path.strip("/").split("/"):
            if not isinstance(node, dict) or part not in node:
                raise error_perm(f"550 {path}")
            node = node[part]
        return node


def _join(cwd: str, name: str) -> str:
    return f"/{name}" if cwd == "/" else f"{cwd}/{name}"


def sd_tree() -> dict:
    return {
        "config": {"ultrahand": {"notifications": {}}},
        "switch": {"soh": {"Save": {"file2.sav": b"{\"slot\":2}", "file1.sav": b"{\"slot\":1}"}}},
        "atmosphere": {},
    }


class EndpointTest(unittest.TestCase):
    def test_accepts_lan_and_rejects_public(self):
        require_private_host("192.168.0.6")
        require_private_host("10.0.0.8")
        require_private_host("127.0.0.1")
        with self.assertRaises(DeviceError):
            require_private_host("8.8.8.8")
        with self.assertRaises(DeviceError):
            require_private_host("ftp://192.168.0.6")

    def test_config_file_fills_missing_flags(self):
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "device.local.json"
            path.write_text(json.dumps({"host": "192.168.0.6", "port": 5000, "user": "anonymous",
                                        "password": "segredo"}), encoding="utf-8")
            endpoint = load_endpoint(host=None, port=None, user=None, password=None, config=path)
            self.assertEqual((endpoint.host, endpoint.port, endpoint.password), ("192.168.0.6", 5000, "segredo"))
            overridden = load_endpoint(host="10.1.1.5", port=2121, user="eu", password="", config=path)
            self.assertEqual((overridden.host, overridden.port, overridden.user, overridden.password),
                             ("10.1.1.5", 2121, "eu", ""))

    def test_sd_mounts_skip_install_and_nand(self):
        self.assertEqual(sd_mounts(["NAND", "SD Card Install", "microSD", "sd"]), ["microSD", "sd"])


class FtpDeviceTest(unittest.TestCase):
    def test_root_is_the_sd(self):
        device = FtpDevice(FakeFtp(sd_tree()))
        self.assertEqual(device.base(), [])
        self.assertEqual(device.locate(SOH_SAVE).names, ["file1.sav", "file2.sav"])

    def test_sd_inside_a_folder(self):
        device = FtpDevice(FakeFtp({"NAND": {}, "microSD": sd_tree()}))
        self.assertEqual(device.base(), ["microSD"])
        self.assertEqual(device.read(f"{SOH_SAVE}/file1.sav"), b"{\"slot\":1}")

    def test_install_folder_is_not_the_sd(self):
        device = FtpDevice(FakeFtp({"SD Card Install": {}, "NAND Install": {}}))
        with self.assertRaises(DeviceError) as caught:
            device.base()
        self.assertIn("SD Card Install", str(caught.exception))

    def test_write_creates_folders_and_read_back(self):
        tree = sd_tree()
        device = FtpDevice(FakeFtp(tree))
        device.write("config/switch-achievements/progress/jogo.json", b"{}")
        self.assertEqual(tree["config"]["switch-achievements"]["progress"]["jogo.json"], b"{}")
        self.assertTrue(device.exists("config/switch-achievements/progress/jogo.json"))
        self.assertIsNone(device.read("config/switch-achievements/state.json"))
        with self.assertRaises(DeviceError):
            device.write("../fora.txt", b"x")

    def test_pull_saves_and_push_notification(self):
        tree = sd_tree()
        fake = FakeFtp(tree)
        device = FtpDevice(fake)
        with tempfile.TemporaryDirectory() as raw:
            saved = device.pull_saves(Path(raw))
            self.assertEqual([path.name for path in saved], ["file1.sav", "file2.sav"])
        remote = device.write(f"{UH_NOTIFICATIONS}/SwitchAchievements-common.trophy-1.notify",
                              json.dumps(test_notification()).encode())
        self.assertTrue(remote.endswith("/config/ultrahand/notifications/SwitchAchievements-common.trophy-1.notify"))
        device.close()
        self.assertTrue(fake.quit_called)
