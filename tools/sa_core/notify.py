"""Gera notificações no formato da API `.notify` do Ultrahand Overlay (>= 2.3).

Referência: https://github.com/ppkantorski/Ultrahand-Overlay/wiki/Command-Reference
No console, os arquivos vão para sdmc:/config/ultrahand/notifications/. O nome
do arquivo escolhe o ícone (ver `layout.ultrahand_app_name`); o som é o
`notification.wav` do Ultrahand, que a instalação troca pelo da conquista.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from .definition import Achievement
from .layout import DEFAULT_ICON, ultrahand_app_name

RARITY_LABEL = {
    "pt-BR": {"common": "Comum", "uncommon": "Incomum", "rare": "Rara", "epic": "Épica", "legendary": "Lendária"},
    "en": {"common": "Common", "uncommon": "Uncommon", "rare": "Rare", "epic": "Epic", "legendary": "Legendary"},
}
TITLE = {"pt-BR": "Conquista desbloqueada", "en": "Achievement unlocked"}


def notification_name(icon_key: str) -> str:
    return f"{ultrahand_app_name(icon_key)}-{time.time_ns()}.notify"


def test_notification() -> dict[str, object]:
    """Toast de teste. Não parece uma conquista desbloqueada de verdade."""
    return {
        "title": "Switch Achievements",
        "text": "Teste pela rede local.\nÍcone e som da conquista instalados.",
        "font_size": 20,
        "alignment": "left",
        "duration": 5000,
        "show_time": "false",
    }


def build_notification(ach: Achievement, lang: str) -> dict[str, object]:
    labels = RARITY_LABEL.get(lang, RARITY_LABEL["en"])
    return {
        "title": TITLE.get(lang, TITLE["en"]),
        "text": f"{ach.text('name', lang)}\n{ach.text('description', lang)}\n+{ach.xp} XP · {labels[ach.rarity]}",
        "font_size": 20,
        "alignment": "left",
        "duration": 5000,
        "show_time": "false",
    }


def write_notification(ach: Achievement, lang: str, directory: Path, icon_key: str = DEFAULT_ICON) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / notification_name(icon_key)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(build_notification(ach, lang), handle, ensure_ascii=False)
    return path
