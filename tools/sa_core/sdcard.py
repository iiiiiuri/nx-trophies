"""Monta `dist/sd/`, o espelho do que vai para o cartão SD.

Instala só o que não muda com o jogo: overlay, ícones, definições e som.
Estado, progresso e perfil ficam fora; quem escreve é o sync (hoje o PC,
depois o sysmodule), para que reinstalar não apague o progresso.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .assets import check_wav, icon_keys
from .catalog import game_files
from .images import png_to_rgba
from .layout import (
    DIST_SD, ICON_SIZE, ICONS_DIR, OVERLAY_BUILD, SD_GAMES, SD_OVERLAY, SD_SOUND, SOUND_FILE, UH_SOUND, icon_file,
    ultrahand_icon_file,
)


@dataclass
class BuildResult:
    root: Path
    files: list[str] = field(default_factory=list)
    overlay: bool = False

    def add(self, relative: str, data: bytes) -> None:
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        self.files.append(relative)


def build_sd(root: Path = DIST_SD, *, icons_dir: Path = ICONS_DIR, sound: Path = SOUND_FILE,
             overlay: Path = OVERLAY_BUILD, with_sound: bool = True) -> BuildResult:
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    result = BuildResult(root)

    for key in icon_keys(icons_dir):
        rgba = png_to_rgba(icons_dir / f"{key}.png", ICON_SIZE)
        result.add(icon_file(key), rgba)
        result.add(ultrahand_icon_file(key), rgba)

    for path in game_files():
        result.add(f"{SD_GAMES}/{path.name}", path.read_bytes())

    if with_sound:
        check_wav(sound)
        data = sound.read_bytes()
        result.add(SD_SOUND, data)
        result.add(UH_SOUND, data)

    if overlay.is_file():
        result.add(SD_OVERLAY, overlay.read_bytes())
        result.overlay = True
    return result
