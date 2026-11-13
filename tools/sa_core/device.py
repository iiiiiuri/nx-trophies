"""FTP na rede local, no lugar do sysmodule, que ainda não existe.

O cliente só fala com IP privado. Os caminhos vêm de `layout` e são relativos
à raiz do cartão. Serve para o FTP do DBI e para o sys-ftpd: o cliente
descobre se a raiz do FTP é o próprio SD ou uma pasta dele (ex.: `microSD`).
"""

from __future__ import annotations

import errno
import ipaddress
import json
import socket
from dataclasses import dataclass
from ftplib import FTP, error_perm
from io import BytesIO
from pathlib import Path

from .layout import REPO_DIR, SOH_SAVE

CONNECT_TIMEOUT = 12
CONFIG_NAME = "device.local.json"
SD_MARKERS = {"atmosphere", "switch", "config"}


class DeviceError(Exception):
    pass


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True)
class Located:
    path: str
    names: list[str]


def require_private_host(host: str) -> None:
    raw = host.strip()
    if not raw or "/" in raw or "@" in raw or any(ord(ch) < 32 for ch in raw):
        raise DeviceError("IP inválido. Exemplo: 192.168.0.6")
    try:
        addresses = [ipaddress.ip_address(raw)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(raw, None)
            addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
        except (socket.gaierror, ValueError) as exc:
            raise DeviceError(f"não resolvi o endereço {raw}") from exc
    if not addresses or not all(_is_local(ip) for ip in addresses):
        raise DeviceError("só conecto em IP da rede local, por exemplo 192.168.0.6")


def _is_local(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return ip.is_private or ip.is_loopback or ip.is_link_local


def config_path(explicit: Path | None) -> Path | None:
    if explicit is not None:
        if not explicit.is_file():
            raise DeviceError(f"não achei {explicit}")
        return explicit
    for candidate in (Path.cwd() / CONFIG_NAME, REPO_DIR / CONFIG_NAME):
        if candidate.is_file():
            return candidate
    return None


def load_endpoint(
    *,
    host: str | None,
    port: int | None,
    user: str | None,
    password: str | None,
    config: Path | None,
) -> Endpoint:
    data: dict[str, object] = {}
    path = config_path(config)
    if path is not None:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DeviceError(f"{path.name} não é JSON válido") from exc
        if not isinstance(loaded, dict):
            raise DeviceError(f"{path.name} precisa ser um objeto")
        data = loaded

    chosen_host = host if host is not None else data.get("host")
    if not isinstance(chosen_host, str) or not chosen_host.strip():
        raise DeviceError("informe --host ou crie device.local.json com host, port, user e password")
    chosen_host = chosen_host.strip()
    require_private_host(chosen_host)

    chosen_port = port if port is not None else data.get("port", 5000)
    if not isinstance(chosen_port, int) or isinstance(chosen_port, bool) or not 1 <= chosen_port <= 65535:
        raise DeviceError("porta inválida")

    raw_user = user if user is not None else data.get("user", "anonymous")
    raw_password = password if password is not None else data.get("password", "")
    if not isinstance(raw_user, str) or not isinstance(raw_password, str):
        raise DeviceError("usuário ou senha inválidos em device.local.json")
    if any(ord(ch) < 32 for ch in raw_user) or any(ord(ch) < 32 for ch in raw_password):
        raise DeviceError("usuário ou senha inválidos")
    return Endpoint(
        host=chosen_host,
        port=chosen_port,
        user=raw_user.strip() or "anonymous",
        password=raw_password,
    )


def connect(endpoint: Endpoint) -> FtpDevice:
    require_private_host(endpoint.host)
    ftp = FTP()
    try:
        ftp.connect(endpoint.host, endpoint.port, timeout=CONNECT_TIMEOUT)
        ftp.login(endpoint.user, endpoint.password)
    except OSError as exc:
        raise DeviceError(_connect_message(endpoint, exc)) from exc
    except error_perm as exc:
        raise DeviceError(f"o FTP recusou o login em {endpoint.host}:{endpoint.port}") from exc
    ftp.set_pasv(True)
    return FtpDevice(ftp)


def _connect_message(endpoint: Endpoint, exc: OSError) -> str:
    where = f"{endpoint.host}:{endpoint.port}"
    if exc.errno == errno.EHOSTUNREACH:
        detail = "sem rota; o console não está nesta rede ou o Wi-Fi dele está desligado"
    elif exc.errno == errno.ECONNREFUSED:
        detail = "a porta recusou; o FTP do Switch não está aberto"
    elif exc.errno in {errno.ETIMEDOUT, errno.EHOSTDOWN}:
        detail = "tempo esgotado; o FTP do Switch não respondeu"
    else:
        detail = exc.strerror or "falha de conexão"
    return f"sem conexão com {where} ({detail})"


def sd_mounts(names: list[str]) -> list[str]:
    """Pastas da raiz que parecem o cartão SD, fora da fila de instalação do DBI."""
    found: list[str] = []
    for name in names:
        low = name.lower()
        if "nand" in low or "install" in low:
            continue
        if any(token in low for token in ("microsd", "sdcard", "sdmc", "sd card", "micro sd")) or low == "sd":
            found.append(name)
    return found


def _parts(relative: str) -> list[str]:
    parts = [part for part in relative.split("/") if part and part != "."]
    if ".." in parts:
        raise DeviceError(f"caminho inválido: {relative}")
    return parts


class FtpDevice:
    def __init__(self, ftp: FTP) -> None:
        self.ftp = ftp
        self._base: list[str] | None = None

    def close(self) -> None:
        try:
            self.ftp.quit()
        except Exception:
            try:
                self.ftp.close()
            except Exception:
                return

    def names_here(self) -> list[str]:
        try:
            raw = self.ftp.nlst()
        except error_perm as exc:
            if "550" in str(exc):
                return []
            raise DeviceError(f"o FTP recusou a listagem ({exc})") from exc
        names: list[str] = []
        for item in raw:
            base = item.rstrip("/").split("/")[-1]
            if base not in {"", ".", ".."}:
                names.append(base)
        return sorted(names)

    def names_at_root(self) -> list[str]:
        self._go_root()
        return self.names_here()

    def base(self) -> list[str]:
        """Pasta do FTP que corresponde a `sdmc:/`."""
        if self._base is not None:
            return self._base
        root_names = self.names_at_root()
        if SD_MARKERS & {name.lower() for name in root_names}:
            self._base = []
            return self._base
        for mount in sd_mounts(root_names):
            try:
                self._descend([mount])
            except error_perm:
                continue
            if SD_MARKERS & {name.lower() for name in self.names_here()}:
                self._base = [mount]
                return self._base
        shown = ", ".join(root_names) or "(vazia)"
        raise DeviceError(
            f"não achei o cartão SD no FTP. Na raiz: {shown}. "
            "O servidor precisa enxergar o SD inteiro (sys-ftpd, ou o FTP do DBI fora da pasta de instalação)."
        )

    def locate(self, relative: str) -> Located:
        try:
            path = self._descend(self.base() + _parts(relative))
        except error_perm as exc:
            raise DeviceError(f"não existe /{relative}") from exc
        return Located(path, self.names_here())

    def exists(self, relative: str) -> bool:
        *folder, name = _parts(relative)
        try:
            self._descend(self.base() + folder)
        except error_perm:
            return False
        return name in self.names_here()

    def read(self, relative: str) -> bytes | None:
        *folder, name = _parts(relative)
        try:
            self._descend(self.base() + folder)
        except error_perm:
            return None
        if name not in self.names_here():
            return None
        out = BytesIO()
        try:
            self.ftp.retrbinary(f"RETR {name}", out.write)
        except error_perm as exc:
            raise DeviceError(f"não baixei /{relative} ({exc})") from exc
        return out.getvalue()

    def write(self, relative: str, data: bytes) -> str:
        *folder, name = _parts(relative)
        if not name:
            raise DeviceError(f"caminho inválido: {relative}")
        remote_dir = self._ensure_dir(folder)
        try:
            self.ftp.storbinary(f"STOR {name}", BytesIO(data))
        except error_perm as exc:
            raise DeviceError(f"não enviei /{relative} ({exc})") from exc
        return f"{remote_dir.rstrip('/')}/{name}"

    def pull_saves(self, dest: Path, folder: str = SOH_SAVE) -> list[Path]:
        try:
            self._descend(self.base() + _parts(folder))
        except error_perm as exc:
            raise DeviceError(f"não existe /{folder}") from exc
        names = [name for name in self.names_here() if name.lower().endswith(".sav")]
        dest.mkdir(parents=True, exist_ok=True)
        saved: list[Path] = []
        for name in names:
            target = dest / name
            try:
                with target.open("wb") as handle:
                    self.ftp.retrbinary(f"RETR {name}", handle.write)
            except error_perm as exc:
                raise DeviceError(f"não baixei {name} ({exc})") from exc
            saved.append(target)
        return saved

    def _ensure_dir(self, folder: list[str]) -> str:
        self._go_root()
        for part in self.base() + folder:
            try:
                self.ftp.cwd(part)
            except error_perm:
                try:
                    self.ftp.mkd(part)
                    self.ftp.cwd(part)
                except error_perm as exc:
                    raise DeviceError(f"não consegui criar a pasta {part} ({exc})") from exc
        return self.ftp.pwd()

    def _descend(self, parts: list[str]) -> str:
        self._go_root()
        for part in parts:
            self.ftp.cwd(part)
        return self.ftp.pwd()

    def _go_root(self) -> None:
        try:
            self.ftp.cwd("/")
        except error_perm:
            return
