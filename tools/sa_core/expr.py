"""Avaliador de expressões e condições para fontes `save_json`.

Implementação de referência: o motor C++ do sysmodule deve reproduzir
exatamente esta semântica (os testes em tools/tests servem de contrato).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

MISSING = object()

_TOKEN = re.compile(r"([^.\[\]]+)|\[(0x[0-9a-fA-F]+|\d+)\]")


class ExprError(ValueError):
    pass


def parse_int(raw: Any) -> int:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw, 0)
        except ValueError as exc:
            raise ExprError(f"inteiro inválido: {raw!r}") from exc
    raise ExprError(f"inteiro inválido: {raw!r}")


def split_path(path: str) -> list[str | int]:
    parts: list[str | int] = []
    pos = 0
    for match in _TOKEN.finditer(path):
        if match.start() != pos and path[pos:match.start()] != ".":
            raise ExprError(f"caminho inválido: {path!r}")
        key, index = match.groups()
        parts.append(key if key is not None else int(index, 0))
        pos = match.end()
    if pos != len(path) or not parts:
        raise ExprError(f"caminho inválido: {path!r}")
    return parts


@dataclass
class Context:
    document: Any
    aliases: dict[str, str] = field(default_factory=dict)
    missing_paths: set[str] = field(default_factory=set)

    def resolve(self, path: str) -> Any:
        parts = split_path(path)
        head = parts[0]
        if isinstance(head, str) and head in self.aliases:
            parts = split_path(self.aliases[head]) + parts[1:]
        node = self.document
        for part in parts:
            if part == "length" and isinstance(node, list):
                node = len(node)
            elif isinstance(part, int) and isinstance(node, list) and 0 <= part < len(node):
                node = node[part]
            elif isinstance(part, str) and isinstance(node, dict) and part in node:
                node = node[part]
            else:
                self.missing_paths.add(path)
                return MISSING
        return node


def _number(value: Any) -> Any:
    if value is MISSING:
        return MISSING
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    return MISSING


def eval_value(expr: Any, ctx: Context) -> Any:
    """Retorna um número ou MISSING."""
    if isinstance(expr, bool):
        return int(expr)
    if isinstance(expr, (int, float)):
        return expr
    if isinstance(expr, str):
        return _number(ctx.resolve(expr))
    if not isinstance(expr, dict) or len(expr) != 1:
        raise ExprError(f"expressão inválida: {expr!r}")

    (op, arg), = expr.items()
    if op == "path":
        return _number(ctx.resolve(arg))
    if op == "const":
        return parse_int(arg)
    if op == "popcount":
        value = eval_value(arg["value"], ctx)
        if value is MISSING:
            return MISSING
        mask = parse_int(arg["mask"]) if "mask" in arg else (1 << 64) - 1
        return bin(int(value) & mask).count("1")
    if op == "sum":
        values = [eval_value(item, ctx) for item in arg]
        return MISSING if any(v is MISSING for v in values) else sum(values)
    if op == "sum_range":
        node = ctx.resolve(arg["path"])
        if not isinstance(node, list):
            ctx.missing_paths.add(arg["path"])
            return MISSING
        start, end = parse_int(arg["from"]), parse_int(arg["to"])
        if end >= len(node):
            ctx.missing_paths.add(f"{arg['path']}[{end}]")
            return MISSING
        values = [_number(v) for v in node[start:end + 1]]
        return MISSING if any(v is MISSING for v in values) else sum(values)
    if op == "div":
        left, right = (eval_value(item, ctx) for item in arg)
        if left is MISSING or right is MISSING or right == 0:
            return MISSING
        return left // right
    raise ExprError(f"operador de valor desconhecido: {op!r}")


_COMPARATORS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "has_all": lambda a, b: (int(a) & int(b)) == int(b),
    "has_any": lambda a, b: (int(a) & int(b)) != 0,
}


def _rhs(raw: Any, ctx: Context) -> Any:
    if isinstance(raw, str):
        return parse_int(raw)
    return eval_value(raw, ctx)


def eval_condition(cond: Any, ctx: Context) -> bool:
    """Avalia uma condição. Valores ausentes tornam a folha falsa."""
    if not isinstance(cond, dict):
        raise ExprError(f"condição inválida: {cond!r}")
    if "all" in cond:
        return all(eval_condition(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(eval_condition(c, ctx) for c in cond["any"])
    if "not" in cond:
        return not eval_condition(cond["not"], ctx)

    op = cond.get("op")
    if op not in _COMPARATORS:
        raise ExprError(f"operador de comparação desconhecido: {op!r}")
    left = eval_value(cond["value"], ctx)
    right = _rhs(cond["rhs"], ctx)
    if left is MISSING or right is MISSING:
        return False
    return _COMPARATORS[op](left, right)
