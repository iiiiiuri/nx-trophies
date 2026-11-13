"""Ícones e som de conquista.

Ícone por convenção, sem campo no JSON do jogo. Para a conquista `boss.gohma`
(gerada pelo template `boss`) de `ship_of_harkinian`, vale o primeiro que existir:

  assets/icons/ship_of_harkinian/boss.gohma.png
  assets/icons/ship_of_harkinian/boss.png
  assets/icons/common/trophy.png

Conquista secreta ainda bloqueada usa `common/secret`.
"""

from __future__ import annotations

import struct
from pathlib import Path

from .definition import Achievement
from .layout import DEFAULT_ICON, ICONS_DIR, SECRET_ICON

WAV_RATES = (8000, 11025, 16000, 22050, 32000, 44100, 48000)


class AssetError(ValueError):
    pass


def icon_key(game_id: str, ach: Achievement, icons_dir: Path = ICONS_DIR) -> str:
    candidates = [f"{game_id}/{ach.id}"]
    if ach.template:
        candidates.append(f"{game_id}/{ach.template}")
    for key in candidates:
        if (icons_dir / f"{key}.png").is_file():
            return key
    return DEFAULT_ICON


def shown_icon_key(game_id: str, ach: Achievement, unlocked: bool, icons_dir: Path = ICONS_DIR) -> str:
    if ach.secret and not unlocked:
        return SECRET_ICON
    return icon_key(game_id, ach, icons_dir)


def icon_keys(icons_dir: Path = ICONS_DIR) -> list[str]:
    return sorted(p.relative_to(icons_dir).with_suffix("").as_posix() for p in icons_dir.rglob("*.png"))


def check_wav(path: Path) -> tuple[int, int]:
    """Confere o que o Ultrahand toca: WAV PCM 16 bits, mono ou estéreo, 8 a 48 kHz."""
    data = path.read_bytes()
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise AssetError(f"{path.name}: não é WAV")
    pos = 12
    while pos + 8 <= len(data):
        kind, size = struct.unpack("<4sI", data[pos:pos + 8])
        if kind == b"fmt ":
            fmt, channels, rate, _, _, bits = struct.unpack("<HHIIHH", data[pos + 8:pos + 24])
            if fmt != 1 or bits != 16:
                raise AssetError(f"{path.name}: precisa ser PCM 16 bits")
            if channels not in (1, 2):
                raise AssetError(f"{path.name}: use mono ou estéreo")
            if rate not in WAV_RATES:
                raise AssetError(f"{path.name}: taxa {rate} Hz; use {', '.join(map(str, WAV_RATES))}")
            return channels, rate
        pos += 8 + size + (size & 1)
    raise AssetError(f"{path.name}: WAV sem bloco fmt")
