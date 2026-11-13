"""Saves sintéticos no formato do Ship of Harkinian (somente campos usados pelo pack)."""

from __future__ import annotations

from typing import Any

COUNT_MAX = 107
TIMESTAMP_MAX = 0xF1
COUNT_ROLLS = 96
COUNT_POTS_BROKEN = 100
COUNT_DARK_LINK = 12


def make_save(
    *,
    equipment: int = 0,
    quest_items: int = 0,
    gs_tokens: int = 0,
    health_capacity: int = 48,
    deaths: int = 0,
    timestamps: dict[int, int] | None = None,
    counts: dict[int, int] | None = None,
    counts_len: int = COUNT_MAX,
    play_timer: int = 0,
    pause_timer: int = 0,
    game_complete: bool = False,
    randomizer: bool = False,
    master_quest: bool = False,
) -> dict[str, Any]:
    item_timestamps = [0] * TIMESTAMP_MAX
    for index, value in (timestamps or {}).items():
        item_timestamps[index] = value
    count_values = [0] * counts_len
    for index, value in (counts or {}).items():
        count_values[index] = value
    return {
        "version": 1,
        "sections": {
            "base": {
                "version": 4,
                "data": {
                    "deaths": deaths,
                    "n64ddFlag": randomizer,
                    "isMasterQuest": master_quest,
                    "healthCapacity": health_capacity,
                    "inventory": {
                        "equipment": equipment,
                        "questItems": quest_items,
                        "gsTokens": gs_tokens,
                    },
                },
            },
            "sohStats": {
                "version": 1,
                "data": {
                    "buildVersionMajor": 9,
                    "buildVersionMinor": 0,
                    "buildVersionPatch": 0,
                    "playTimer": play_timer,
                    "pauseTimer": pause_timer,
                    "gameComplete": game_complete,
                    "itemTimestamps": item_timestamps,
                    "counts": count_values,
                },
            },
        },
    }


def early_game() -> dict[str, Any]:
    """Espada Kokiri, Ocarina das Fadas, Gohma em 25 min, uma morte."""
    return make_save(
        equipment=0x0011,
        quest_items=(1 << 18) | (1 << 12) | (1 << 14),
        gs_tokens=7,
        deaths=1,
        timestamps={0x07: 9000, 0xA0: 15000},
        counts={COUNT_ROLLS: 412, COUNT_POTS_BROKEN: 58, 0: 3, 44: 20},
        play_timer=2 * 18000,
    )


def late_game() -> dict[str, Any]:
    """Jogo zerado sem mortes, todos os medalhões e pedras, 11h de jogo."""
    return make_save(
        equipment=0x7777,
        quest_items=0x1FFFFF,
        gs_tokens=63,
        health_capacity=16 * 17,
        deaths=0,
        timestamps={0x07: 9000, 0xA0: 21000, 0xA1: 40000, 0xA2: 60000, 0xA3: 120000, 0xA4: 150000,
                    0xA5: 200000, 0xA6: 260000, 0xA7: 300000, 0xA9: 390000},
        counts={COUNT_ROLLS: 3500, COUNT_POTS_BROKEN: 280, COUNT_DARK_LINK: 1, 44: 300, 60: 250},
        play_timer=2 * 380000,
        pause_timer=3 * 20000,
        game_complete=True,
    )
