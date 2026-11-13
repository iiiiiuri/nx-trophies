"""Monta `dist/sd/`, o espelho do que vai para o cartão SD, e a release.

Instala só o que não muda com o jogo: app, sysmodule, overlay, pacotes,
ícones, capas e som. Estado, progresso e perfil ficam fora; quem escreve é
o sysmodule, para que reinstalar ou atualizar não apague o progresso.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .assets import check_wav, icon_keys
from .catalog import load_catalog
from .images import png_to_rgba
from .layout import (
    APP_BUILD, COVERS_DIR, DIST_SD, ICON_SIZE, ICONS_DIR, OVERLAY_BUILD, RELEASE_ASSET, RELEASE_DIR, SD_APP, SD_COVERS,
    SD_OVERLAY, SD_SOUND, SD_SYSMODULE, SD_SYSMODULE_BOOT, SD_SYSMODULE_TOOLBOX, SD_VERSION, SOUND_FILE, SYSMODULE_BUILD,
    SYSMODULE_ID, UH_SOUND, icon_file, icon_png_file, pack_file, ultrahand_icon_file,
)
from .pack import compile_pack, pack_bytes

TOOLBOX = {"name": "Switch Achievements", "tid": SYSMODULE_ID, "requires_reboot": False}


class BuildError(RuntimeError):
    pass


@dataclass
class BuildResult:
    root: Path
    files: list[str] = field(default_factory=list)
    binaries: list[str] = field(default_factory=list)
    contents: dict[str, Any] = field(default_factory=dict)

    def add(self, relative: str, data: bytes) -> None:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.files.append(relative)


def build_sd(root: Path = DIST_SD, *, version: str = "dev", icons_dir: Path = ICONS_DIR, covers_dir: Path = COVERS_DIR,
             sound: Path = SOUND_FILE, overlay: Path = OVERLAY_BUILD, sysmodule: Path = SYSMODULE_BUILD,
             app: Path = APP_BUILD, with_sound: bool = True, require_binaries: bool = False) -> BuildResult:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    result = BuildResult(root)
    components: dict[str, str] = {}
    art = hashlib.sha256()

    for key in icon_keys(icons_dir):
        source = icons_dir / f"{key}.png"
        rgba = png_to_rgba(source, ICON_SIZE)
        result.add(icon_file(key), rgba)
        result.add(ultrahand_icon_file(key), rgba)
        result.add(icon_png_file(key), source.read_bytes())
        art.update(key.encode() + rgba)

    if covers_dir.is_dir():
        for cover in sorted(covers_dir.glob("*.png")):
            data = cover.read_bytes()
            result.add(f"{SD_COVERS}/{cover.name}", data)
            art.update(cover.name.encode() + data)
    components["art"] = art.hexdigest()[:12]

    catalog = load_catalog()
    if catalog.problems:
        raise BuildError("definições inválidas: " + "; ".join(catalog.problems))
    games = []
    for game_id, definition in sorted(catalog.games.items()):
        pack = compile_pack(definition, icons_dir)
        result.add(pack_file(game_id), pack_bytes(pack))
        games.append({"id": game_id, "name": definition.name.get("pt-BR") or next(iter(definition.name.values())),
                      "achievements": len(pack["achievements"]), "rev": pack["rev"]})

    if with_sound:
        check_wav(sound)
        data = sound.read_bytes()
        result.add(SD_SOUND, data)
        result.add(UH_SOUND, data)
        components["sound"] = _digest(data)

    for label, source, target in (("overlay", overlay, SD_OVERLAY), ("sysmodule", sysmodule, SD_SYSMODULE),
                                  ("app", app, SD_APP)):
        if source.is_file():
            data = source.read_bytes()
            result.add(target, data)
            result.binaries.append(label)
            components[label] = _digest(data)
        elif require_binaries:
            raise BuildError(f"{label} não compilado: {source}")
    if "sysmodule" in result.binaries:
        result.add(SD_SYSMODULE_BOOT, b"")
        result.add(SD_SYSMODULE_TOOLBOX, json.dumps(TOOLBOX, indent=2).encode())

    result.contents = {"games": games, "components": components}
    result.add(SD_VERSION, json.dumps({"version": version, "contents": result.contents}, ensure_ascii=False).encode())
    return result


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def build_release(version: str, notes: str = "", out: Path = RELEASE_DIR) -> tuple[Path, Path]:
    """Gera o zip do SD e o manifest.json que o app lê em releases/latest."""
    sd = build_sd(out / "sd", version=version, require_binaries=True)
    zip_path = out / RELEASE_ASSET
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in sorted(sd.files):
            info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, (sd.root / relative).read_bytes())
    data = zip_path.read_bytes()
    manifest = {
        "version": version,
        "asset": RELEASE_ASSET,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "notes": notes,
        "contents": sd.contents,
    }
    manifest_path = out / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return zip_path, manifest_path
