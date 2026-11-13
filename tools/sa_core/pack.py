"""Pacote compilado: a definição de um jogo pronta para o motor nativo.

O sysmodule não entende templates, agregados de conteúdo, aliases nem nomes
de variável. Este módulo resolve tudo isso uma vez, no PC (ou no CI), e
grava um JSON enxuto que o C++ só executa:

- `vars`: nomes de todas as instâncias; o resto do pacote usa o índice.
- condições e valores viram árvores com índices (`{"v": i}`, `{"c": e}`).
- cada binding traz seus blocos de leitura (memória) ou caminhos (save).
- inteiros acima de 2^53 viram string hex, porque o cJSON guarda double.

A semântica é a de `expr.py` e `engine.py`; os testes comparam as duas.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .assets import icon_key
from .definition import Binding, Definition, Readiness, build_index
from .expr import parse_int
from .layout import ICONS_DIR
from .sources import _split_path

PACK_FORMAT = 1
_EXACT_LIMIT = 1 << 53
READINESS_NAME = {
    Readiness.LIVE: "live",
    Readiness.REHEARSAL: "rehearsal",
    Readiness.PENDING: "pending",
    Readiness.UNSUPPORTED: "unsupported",
}


def _int(value: int) -> int | str:
    return value if -_EXACT_LIMIT < value < _EXACT_LIMIT else hex(value & ((1 << 64) - 1))


class _Compiler:
    def __init__(self, var_names: list[str], event_ids: list[str]):
        self.var_names = list(var_names)
        self.var_index = {name: i for i, name in enumerate(var_names)}
        self.event_index = {name: i for i, name in enumerate(event_ids)}

    def var(self, name: str) -> int:
        if name not in self.var_index:
            self.var_index[name] = len(self.var_names)
            self.var_names.append(name)
        return self.var_index[name]

    def value(self, expr: Any) -> Any:
        if isinstance(expr, bool):
            return int(expr)
        if isinstance(expr, int):
            return _int(expr)
        if isinstance(expr, float):
            return expr
        if isinstance(expr, str):
            return {"v": self.var(expr)}
        (op, arg), = expr.items()
        if op == "var":
            return {"v": self.var(arg)}
        if op == "const":
            return _int(parse_int(arg))
        if op == "count":
            return {"c": self.event_index[arg]}
        if op == "truth":
            return {"t": self.cond(arg)}
        if op == "popcount":
            node = {"pop": self.value(arg["value"])}
            if "mask" in arg:
                node["mask"] = _int(parse_int(arg["mask"]))
            return node
        if op in ("sum", "div"):
            return {op: [self.value(item) for item in arg]}
        raise ValueError(f"operador de valor desconhecido: {op!r}")

    def cond(self, cond: dict[str, Any]) -> dict[str, Any]:
        for group in ("all", "any"):
            if group in cond:
                return {group: [self.cond(c) for c in cond[group]]}
        if "not" in cond:
            return {"not": self.cond(cond["not"])}
        if "exists" in cond:
            return {"exists": self.var(cond["exists"])}
        rhs = cond["rhs"]
        right = _int(parse_int(rhs)) if isinstance(rhs, str) else self.value(rhs)
        return {"op": cond["op"], "l": self.value(cond["value"]), "r": right}


def _path_tokens(path: str, binding: Binding) -> list[str | int]:
    parts = _split_path(path)
    if parts and isinstance(parts[0], str) and parts[0] in binding.aliases:
        parts = _split_path(binding.aliases[parts[0]]) + parts[1:]
    return parts


def _compile_binding(definition: Definition, binding: Binding, comp: _Compiler) -> dict[str, Any]:
    index = build_index(definition, binding)
    pointer_ids = list(binding.pointers)
    out: dict[str, Any] = {
        "id": binding.id,
        "source": binding.source,
        "build_ids": [b.upper() for b in binding.build_ids],
        "files": list(binding.files),
        "poll_ms": binding.poll_ms,
        "active_when": comp.cond(binding.active_when) if binding.active_when else None,
        "modes": [{"name": name, "cond": comp.cond(cond)} for name, cond in binding.instance_modes.items()],
        "ready": [READINESS_NAME[index.readiness[ach.id]] for ach in index.achievements],
    }
    if binding.source == "memory":
        out["pointers"] = [{"region": p.region, "chain": [_int(o) for o in p.chain]}
                           for p in binding.pointers.values()]
        blocks = []
        for block in index.read_plan:
            kind, name = block.anchor.split(":", 1)
            anchor: str | int = pointer_ids.index(name) if kind == "ptr" else name
            fields = []
            for var_name in block.variables:
                inst = index.instances[var_name]
                fields.append([comp.var(var_name), inst.offset - block.offset, inst.type])
            blocks.append({"anchor": anchor, "offset": _int(block.offset), "size": block.size, "vars": fields})
        out["blocks"] = blocks
    else:
        out["paths"] = [[comp.var(inst.name), _path_tokens(inst.path, binding)]
                        for inst in index.instances.values() if inst.path is not None]
    return out


def compile_pack(definition: Definition, icons_dir: Path = ICONS_DIR) -> dict[str, Any]:
    instance_names: set[str] = set()
    for binding in definition.bindings.values():
        instance_names |= set(build_index(definition, binding).instances)
    comp = _Compiler(sorted(instance_names), list(definition.events))

    achievements = []
    for ach in definition.achievements:
        progress = None
        if ach.progress is not None:
            progress = {"value": comp.value(ach.progress["value"]), "target": parse_int(ach.progress["target"])}
        achievements.append({
            "id": ach.id,
            "name": ach.name,
            "desc": ach.description,
            "xp": ach.xp,
            "rarity": ach.rarity,
            "secret": ach.secret,
            "icon": icon_key(definition.game_id, ach, icons_dir),
            "modes": list(ach.modes) if ach.modes is not None else None,
            "confirm": ach.confirm_ticks,
            "progress": progress,
            "cond": comp.cond(ach.condition),
        })

    pack = {
        "format": PACK_FORMAT,
        "game": definition.game_id,
        "name": definition.name,
        "kind": definition.kind,
        "title_ids": [t.upper() for t in definition.title_ids],
        "events": [{"id": e.id, "when": comp.cond(e.when)} for e in definition.events.values()],
        "bindings": [_compile_binding(definition, b, comp) for b in definition.bindings.values()],
        "achievements": achievements,
    }
    pack["vars"] = comp.var_names
    pack["rev"] = hashlib.sha1(pack_bytes(pack)).hexdigest()[:12]
    return pack


def pack_bytes(pack: dict[str, Any]) -> bytes:
    return json.dumps(pack, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
