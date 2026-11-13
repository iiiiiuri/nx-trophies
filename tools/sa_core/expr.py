"""Linguagem de condições, comum a todos os jogos e fontes.

As condições só enxergam *variáveis* (nomes declarados na definição do jogo)
e *contadores de eventos*. De onde o valor vem (memória, save, sistema) é
problema do binding; por isso a mesma conquista funciona em qualquer fonte.

Implementação de referência: o motor C++ do sysmodule deve reproduzir esta
semântica (os testes em tools/tests são o contrato).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

MISSING = object()


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


@dataclass
class Context:
    values: dict[str, Any]
    counters: dict[str, int] = field(default_factory=dict)

    def var(self, name: str) -> Any:
        value = self.values.get(name, MISSING)
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
        return ctx.var(expr)
    if not isinstance(expr, dict) or len(expr) != 1:
        raise ExprError(f"expressão inválida: {expr!r}")

    (op, arg), = expr.items()
    if op == "var":
        return ctx.var(arg)
    if op == "const":
        return parse_int(arg)
    if op == "count":
        return ctx.counters.get(arg, 0)
    if op == "truth":
        return int(eval_condition(arg, ctx))
    if op == "popcount":
        value = eval_value(arg["value"], ctx)
        if value is MISSING:
            return MISSING
        mask = parse_int(arg["mask"]) if "mask" in arg else (1 << 64) - 1
        return bin(int(value) & mask).count("1")
    if op == "sum":
        values = [eval_value(item, ctx) for item in arg]
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
    if "exists" in cond:
        return ctx.var(cond["exists"]) is not MISSING

    op = cond.get("op")
    if op not in _COMPARATORS:
        raise ExprError(f"operador de comparação desconhecido: {op!r}")
    left = eval_value(cond["value"], ctx)
    right = _rhs(cond["rhs"], ctx)
    if left is MISSING or right is MISSING:
        return False
    return _COMPARATORS[op](left, right)


@dataclass
class References:
    variables: set[str] = field(default_factory=set)
    events: set[str] = field(default_factory=set)


def _collect_value(expr: Any, refs: References) -> None:
    if isinstance(expr, str):
        refs.variables.add(expr)
    elif isinstance(expr, dict) and len(expr) == 1:
        (op, arg), = expr.items()
        if op == "var":
            refs.variables.add(arg)
        elif op == "count":
            refs.events.add(arg)
        elif op == "truth":
            collect_references(arg, refs)
        elif op == "popcount":
            _collect_value(arg["value"], refs)
        elif op in ("sum", "div"):
            for item in arg:
                _collect_value(item, refs)


def collect_references(cond: Any, refs: References | None = None) -> References:
    """Lista variáveis e eventos usados por uma condição (para indexação)."""
    refs = refs or References()
    if not isinstance(cond, dict):
        return refs
    for group in ("all", "any"):
        if group in cond:
            for child in cond[group]:
                collect_references(child, refs)
            return refs
    if "not" in cond:
        return collect_references(cond["not"], refs)
    if "exists" in cond:
        refs.variables.add(cond["exists"])
        return refs
    _collect_value(cond.get("value"), refs)
    if not isinstance(cond.get("rhs"), str):
        _collect_value(cond.get("rhs"), refs)
    return refs
