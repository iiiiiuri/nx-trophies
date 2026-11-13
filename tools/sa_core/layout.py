"""Onde cada coisa mora: no repositório e no cartão SD do Switch.

Tudo que é do projeto fica em `sdmc:/config/switch-achievements/`. Fora dele
só ficam os pontos que o Ultrahand exige: pasta de notificações, ícone por
APP_ID e o som de notificação. O overlay vai na pasta padrão de overlays.
Caminhos do SD são relativos à raiz do cartão, sem `sdmc:/`.
"""

from __future__ import annotations

from pathlib import Path

APP_ID = "SwitchAchievements"

REPO_DIR = Path(__file__).resolve().parents[2]
ASSETS_DIR = REPO_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
SOUND_FILE = ASSETS_DIR / "sounds" / "achievement.wav"
OVERLAY_BUILD = REPO_DIR / "overlay" / "switch-achievements.ovl"
DIST_SD = REPO_DIR / "dist" / "sd"
DEVICE_CACHE = REPO_DIR / "device-cache"

SD_ROOT = "config/switch-achievements"
SD_STATE = f"{SD_ROOT}/state.json"
SD_PROFILE = f"{SD_ROOT}/profile.json"
SD_PROGRESS = f"{SD_ROOT}/progress"
SD_ICONS = f"{SD_ROOT}/icons"
SD_GAMES = f"{SD_ROOT}/games"
SD_SOUND = f"{SD_ROOT}/sounds/achievement.wav"
SD_BACKUP = f"{SD_ROOT}/backup"
SD_OVERLAY = "switch/.overlays/switch-achievements.ovl"

UH_NOTIFICATIONS = "config/ultrahand/notifications"
UH_ICONS = "config/ultrahand/assets/notifications"
UH_SOUND = "config/ultrahand/sounds/notification.wav"
UH_SOUND_BACKUP = f"{SD_BACKUP}/ultrahand-notification.wav"

SOH_SAVE = "switch/soh/Save"

ICON_SIZE = 50
DEFAULT_ICON = "common/trophy"
SECRET_ICON = "common/secret"


def progress_file(game_id: str) -> str:
    return f"{SD_PROGRESS}/{game_id}.json"


def icon_file(icon_key: str) -> str:
    """`ship_of_harkinian/boss` -> config/switch-achievements/icons/ship_of_harkinian/boss.rgba"""
    return f"{SD_ICONS}/{icon_key}.rgba"


def ultrahand_app_name(icon_key: str) -> str:
    """Nome que o Ultrahand associa ao ícone.

    O Ultrahand tira do nome do `.notify` o que vem antes do último `-` e busca
    `assets/notifications/<isso>.rgba`; o filtro por app usa o que vem antes do
    primeiro `-`. Com `SwitchAchievements-<jogo>.<ícone>` os dois funcionam.
    """
    return f"{APP_ID}-{icon_key.replace('/', '.')}"


def ultrahand_icon_file(icon_key: str) -> str:
    return f"{UH_ICONS}/{ultrahand_app_name(icon_key)}.rgba"
