"""Traces de memória simulada para MK8 Deluxe e Link's Awakening.

Os endereços seguem os bindings das definições; as bases das regiões são
arbitrárias (ASLR), por isso tudo é relativo a `main`/ponteiros.
"""

from __future__ import annotations

from typing import Any

MAIN_BASE = "0x8000000"
HEAP_BASE = "0x40000000"
REGIONS = {
    "main": {"base": MAIN_BASE, "size": "0x2000000"},
    "heap": {"base": HEAP_BASE, "size": "0x10000000"},
}
KART_HOLDER = 0x40001000
KART = 0x40100000


def _w(addr: str | int, var_type: str, value: Any) -> dict[str, Any]:
    if isinstance(addr, int):
        addr = hex(addr)
    return {"addr": addr, "type": var_type, "value": value}


def kart(offset: int, value: int) -> dict[str, Any]:
    return _w(KART + offset, "u32", value)


def mk8_race() -> dict[str, Any]:
    pointers = [_w("main+0x1354AF0", "u64", KART_HOLDER), _w(KART_HOLDER + 0x6E0, "u64", KART)]
    normal, bullet = 0x00801000, 0x00A01000
    ticks = [
        {"label": "menu: kart ainda não existe", "writes": []},
        {"label": "corrida começa", "writes": pointers + [kart(0x7A4, normal)]},
        {"label": "pegou Superestrela", "writes": [kart(0x7BC, 0x1BF)]},
        {"label": "estrela ainda ativa", "writes": [kart(0x7BC, 0x100)]},
        {"label": "estrela acabou", "writes": [kart(0x7BC, 0)]},
        {"label": "atingido por Raio", "writes": [kart(0x7FC, 0x175)]},
        {"label": "choque acabou", "writes": [kart(0x7FC, 0)]},
        {"label": "caiu da pista, Lakitu", "writes": [kart(0x830, 0x1BF)]},
        {"label": "de volta à pista", "writes": [kart(0x830, 0)]},
        {"label": "virou Bullet Bill", "writes": [kart(0x7A4, bullet)]},
        {"label": "Bullet Bill acabou", "writes": [kart(0x7A4, normal)]},
        {"label": "segunda Superestrela", "writes": [kart(0x7BC, 0x1BF)]},
        {"label": "estrela acabou", "writes": [kart(0x7BC, 0)]},
        {"label": "fim da corrida: volta ao menu", "writes": [_w(KART_HOLDER + 0x6E0, "u64", 0)]},
        {"label": "menu (lixo onde era o kart não conta)", "writes": [kart(0x7BC, 0x1BF)]},
    ]
    return {"build_id": "FE941ED5BA14BE5D", "regions": REGIONS, "initial": [], "ticks": ticks}


def mk8_race_aarch32() -> dict[str, Any]:
    """3.0.1: ponteiros de 4 bytes; a palavra seguinte com lixo não pode atrapalhar."""
    holder, kart_base = 0x40002000, 0x40200000

    def k(offset: int, value: int) -> dict[str, Any]:
        return _w(kart_base + offset, "u32", value)

    pointers = [_w("main+0xF53448", "u32", holder), _w("main+0xF5344C", "u32", 0xDEADBEEF),
                _w(holder + 0x1350, "u32", kart_base)]
    ticks = [
        {"label": "menu", "writes": [_w("main+0xF5344C", "u32", 0xDEADBEEF)]},
        {"label": "corrida começa", "writes": pointers + [k(0x9D8, 0x00801000)]},
        {"label": "fantasma (Boo)", "writes": [k(0x9F8, 0x120)]},
        {"label": "fantasma acabou", "writes": [k(0x9F8, 0)]},
        {"label": "achatado", "writes": [k(0xA28, 0x120)]},
        {"label": "fim da corrida", "writes": [_w(holder + 0x1350, "u32", 0)]},
    ]
    return {"build_id": "9EF5CAA2D5B933C7", "regions": REGIONS, "initial": [], "ticks": ticks}


def la(offset: int, var_type: str, value: int) -> dict[str, Any]:
    return _w(f"main+{hex(offset)}", var_type, value)


def la_progress() -> dict[str, Any]:
    rupees, trade, follower, leaves, figures = 0x1CC0760, 0x1CC077A, 0x1CC077D, 0x1CC07A2, 0x1CC07C8
    treasures, key_items = 0x1CBB301, 0x1CC078C
    ticks = [
        {"label": "início do arquivo", "writes": []},
        {"label": "Boneco do Yoshi no jogo de garra", "writes": [la(trade, "u8", 1), la(rupees, "u16", 120)]},
        {"label": "CiaoCiao e Goomba", "writes": [la(figures, "u16", 0x0003)]},
        {"label": "Laço", "writes": [la(trade, "u8", 2)]},
        {"label": "Ração de Cachorro", "writes": [la(trade, "u8", 3)]},
        {"label": "Caverna da Cauda: mapa, bússola, bico, chave", "writes": [la(treasures, "u8", 0x0F)]},
        {"label": "Violoncelo da Lua Cheia (nadadeiras e Tail Key já no inventário)",
         "writes": [la(key_items, "u32", 0x0085)]},
        {"label": "Marin acompanha", "writes": [la(follower, "u8", 1)]},
        {"label": "Marin volta para casa", "writes": [la(follower, "u8", 0)]},
        {"label": "Bananas", "writes": [la(trade, "u8", 4)]},
        {"label": "3 folhas douradas", "writes": [la(leaves, "u8", 0x07)]},
        {"label": "mais figurinhas", "writes": [la(figures, "u16", 0x020F)]},
        {"label": "5 folhas douradas", "writes": [la(leaves, "u8", 0x1F)]},
        {"label": "rúpias no máximo", "writes": [la(rupees, "u16", 999)]},
        {"label": "oito instrumentos", "writes": [la(key_items, "u32", 0x1FFFF)]},
    ]
    return {"build_id": "909E904AF78AC1B8", "regions": REGIONS, "initial": [], "ticks": ticks}
