"""Definição de jogo (JSON) -> índice observável.

Uma definição tem cinco camadas, nenhuma com código específico de jogo:

  content      catálogo do jogo (copas, masmorras, itens...) com as chaves
               que o jogo usa na memória (índice, bit, valor)
  variables    estado abstrato observável, opcionalmente indexado por um
               conjunto de conteúdo (ex.: dungeon.items[tail_cave])
  bindings     onde cada variável mora, por build do jogo (memória) ou por
               formato de arquivo (save), com nível de confiança
  events       transições (bordas) sobre variáveis, contadas pelo motor
  achievements conquistas, explícitas ou geradas por template (for_each)

`build_index` combina definição + binding ativo em um `Index`: instâncias de
variáveis resolvidas, conquistas expandidas com prontidão calculada e o
plano de leitura em blocos que o sysmodule executa a cada tick.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

from .expr import ExprError, Context, collect_references, eval_condition, eval_value, parse_int

SCHEMA_VERSION = 2
RARITIES = ("common", "uncommon", "rare", "epic", "legendary")
DEFAULT_XP = {"common": 10, "uncommon": 25, "rare": 50, "epic": 100, "legendary": 250}
TYPE_SIZES = {"u8": 1, "s8": 1, "u16": 2, "s16": 2, "u32": 4, "s32": 4, "u64": 8, "s64": 8, "f32": 4, "f64": 8}
MEMORY_REGIONS = ("main", "heap", "alias", "aslr")
MAX_ACHIEVEMENTS = 512
MAX_CHAIN_DEPTH = 8
MAX_BLOCK = 0x1000
GAME_KINDS = ("retail", "homebrew")
SOURCES = ("memory", "save_json")
_PLACEHOLDER = re.compile(r"\{item\.([a-zA-Z0-9_]+)\}")
_EACH_PLACEHOLDER = re.compile(r"\{each\.([a-zA-Z0-9_]+)\}")
GAME_ID = re.compile(r"[a-z0-9][a-z0-9_]*")
HEX16 = re.compile(r"[0-9A-Fa-f]{16}")
IDENTIFIER = re.compile(r"[a-z0-9][a-z0-9_.]*")

# Estrutura padrão: qualquer chave fora destas listas é erro de digitação.
# Entradas de `content` são livres (cada jogo tem suas chaves), exceto `id`.
ALLOWED_KEYS = {
    "definição": {"$schema", "schema_version", "game", "content", "variables", "bindings", "events", "achievements"},
    "game": {"id", "name", "kind", "title_ids", "notes"},
    "variável": {"type", "indexed_by", "description"},
    "binding": {"id", "label", "source", "match", "pointers", "active_when", "aliases", "instance_modes",
                "poll_ms", "variables", "notes"},
    "match": {"build_ids", "files"},
    "ponteiro": {"base", "chain", "note"},
    "variável do binding": {"base", "from", "offset", "stride", "index_key", "path", "type", "confidence", "note"},
    "evento": {"id", "when", "description"},
    "conquista": {"id", "name", "description", "xp", "rarity", "secret", "condition", "progress", "modes",
                  "confirm_ticks", "for_each", "where_has"},
}


class DefinitionError(ValueError):
    pass


class Confidence(IntEnum):
    """Ordem importa: a prontidão de uma conquista é a menor confiança usada."""

    TO_DISCOVER = 0   # endereço desconhecido: conquista desativada
    ASSUMED = 1       # inferido, não confirmado: modo ensaio (loga, não desbloqueia)
    COMMUNITY = 2     # vindo de cheats/documentação pública: ativo
    VERIFIED = 3      # confirmado no console pelo projeto: ativo

    @classmethod
    def parse(cls, raw: str) -> "Confidence":
        try:
            return cls[raw.upper()]
        except KeyError as exc:
            raise DefinitionError(f"confiança inválida: {raw!r}") from exc


class Readiness(IntEnum):
    UNSUPPORTED = 0   # o binding não declara uma variável usada
    PENDING = 1       # depende de endereço ainda não descoberto
    REHEARSAL = 2     # avalia e registra no log, sem desbloquear
    LIVE = 3


@dataclass(frozen=True)
class Pointer:
    id: str
    region: str
    chain: tuple[int, ...]


@dataclass(frozen=True)
class VarInstance:
    name: str
    type: str
    confidence: Confidence
    region: str | None = None
    pointer: str | None = None
    offset: int | None = None
    path: str | None = None
    note: str | None = None

    @property
    def size(self) -> int:
        return TYPE_SIZES[self.type]


@dataclass(frozen=True)
class Binding:
    id: str
    label: str
    source: str
    build_ids: tuple[str, ...]
    files: tuple[str, ...]
    aliases: dict[str, str]
    pointers: dict[str, Pointer]
    active_when: dict[str, Any] | None
    instance_modes: dict[str, dict[str, Any]]
    poll_ms: int
    raw_variables: dict[str, Any]


@dataclass(frozen=True)
class Event:
    id: str
    when: dict[str, Any]
    content_confidence: Confidence = Confidence.VERIFIED


@dataclass(frozen=True)
class Achievement:
    id: str
    name: dict[str, str]
    description: dict[str, str]
    xp: int
    rarity: str
    secret: bool
    condition: dict[str, Any]
    progress: dict[str, Any] | None
    modes: tuple[str, ...] | None
    confirm_ticks: int
    template: str | None
    content_confidence: Confidence = Confidence.VERIFIED

    def text(self, field_name: str, lang: str) -> str:
        values = getattr(self, field_name)
        return values.get(lang) or values.get("en") or next(iter(values.values()))


@dataclass(frozen=True)
class ReadBlock:
    """Uma leitura contígua por tick. `anchor` é a região ou o ponteiro base."""

    anchor: str
    offset: int
    size: int
    variables: tuple[str, ...]


@dataclass
class Definition:
    game_id: str
    name: dict[str, str]
    kind: str
    title_ids: tuple[str, ...]
    content: dict[str, list[dict[str, Any]]]
    variables: dict[str, dict[str, Any]]
    bindings: dict[str, Binding]
    events: dict[str, Event]
    achievements: list[Achievement]

    def binding_for_build(self, build_id: str) -> Binding | None:
        wanted = build_id.upper()
        for binding in self.bindings.values():
            if any(b.upper() == wanted for b in binding.build_ids):
                return binding
        return None

    def text(self, lang: str) -> str:
        return self.name.get(lang) or self.name.get("en") or next(iter(self.name.values()))


@dataclass
class Index:
    definition: Definition
    binding: Binding
    instances: dict[str, VarInstance]
    events: dict[str, Event]
    achievements: list[Achievement]
    readiness: dict[str, Readiness]
    blockers: dict[str, list[str]]
    read_plan: list[ReadBlock] = field(default_factory=list)

    def by_id(self, achievement_id: str) -> Achievement:
        for ach in self.achievements:
            if ach.id == achievement_id:
                return ach
        raise KeyError(achievement_id)


# --------------------------------------------------------------------------
# carregamento


def _require(obj: dict[str, Any], key: str, where: str) -> Any:
    if not isinstance(obj, dict) or key not in obj:
        raise DefinitionError(f"{where}: campo obrigatório ausente: {key!r}")
    return obj[key]


def _check_keys(obj: Any, kind: str, where: str) -> None:
    if not isinstance(obj, dict):
        raise DefinitionError(f"{where}: esperado um objeto")
    unknown = set(obj) - ALLOWED_KEYS[kind]
    if unknown:
        raise DefinitionError(f"{where}: chave(s) desconhecida(s) {sorted(unknown)}; "
                              f"permitidas: {sorted(ALLOWED_KEYS[kind])}")


def _check_pattern(value: Any, pattern: re.Pattern[str], where: str, what: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise DefinitionError(f"{where}: {what} inválido {value!r}")
    return value


def _localized(raw: Any, where: str) -> dict[str, str]:
    if isinstance(raw, str):
        return {"en": raw}
    if isinstance(raw, dict) and raw and all(isinstance(v, str) for v in raw.values()):
        return dict(raw)
    raise DefinitionError(f"{where}: texto deve ser string ou mapa idioma -> string")


def _substitute(node: Any, item: dict[str, Any], lang: str | None = None, prefix: str = "item") -> Any:
    """Troca {item.campo} (ou {each.campo}) por valores da entrada de conteúdo.

    Uma string que é só o placeholder vira o valor com o tipo original
    (número continua número). Nomes localizados usam o idioma pedido.
    """
    if isinstance(node, dict):
        return {k: _substitute(v, item, lang, prefix) for k, v in node.items()}
    if isinstance(node, list):
        return [_substitute(v, item, lang, prefix) for v in node]
    if not isinstance(node, str):
        return node
    pattern = _PLACEHOLDER if prefix == "item" else _EACH_PLACEHOLDER

    def lookup(key: str) -> Any:
        if key not in item:
            raise DefinitionError(f"placeholder {{{prefix}.{key}}} sem valor na entrada {item.get('id')!r}")
        value = item[key]
        if isinstance(value, dict):
            return value.get(lang or "en") or value.get("en") or next(iter(value.values()))
        return value

    whole = pattern.fullmatch(node)
    if whole:
        return lookup(whole.group(1))
    return pattern.sub(lambda m: str(lookup(m.group(1))), node)


def _entries(content: dict[str, list[dict[str, Any]]], set_name: str, where: str) -> list[dict[str, Any]]:
    if set_name not in content:
        raise DefinitionError(f"{where}: conjunto de conteúdo desconhecido {set_name!r}")
    return content[set_name]


def _resolve_content(node: Any, content: dict[str, list[dict[str, Any]]], used: list[Confidence]) -> Any:
    """Expande agregados sobre conteúdo: content_mask, for_all, for_any, count_of.

    `used` acumula a confiança das entradas de conteúdo envolvidas.
    """
    if isinstance(node, list):
        return [_resolve_content(v, content, used) for v in node]
    if not isinstance(node, dict):
        return node
    if set(node) == {"content_mask"}:
        spec = node["content_mask"]
        mask = 0
        for entry in _entries(content, spec["of"], "content_mask"):
            if spec.get("key", "mask") in entry:
                mask |= parse_int(entry[spec.get("key", "mask")])
                used.append(Confidence.parse(entry.get("confidence", "verified")))
        return mask
    for aggregate in ("for_all", "for_any", "count_of"):
        if aggregate in node:
            entries = _entries(content, node[aggregate], aggregate)
            parts = []
            for entry in entries:
                used.append(Confidence.parse(entry.get("confidence", "verified")))
                parts.append(_resolve_content(_substitute(node["condition"], entry, prefix="each"), content, used))
            if aggregate == "for_all":
                return {"all": parts}
            if aggregate == "for_any":
                return {"any": parts}
            return {"sum": [{"truth": p} for p in parts]}
    return {k: _resolve_content(v, content, used) for k, v in node.items()}


def _normalize_content(raw: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    content: dict[str, list[dict[str, Any]]] = {}
    for set_name, entries in raw.items():
        _check_pattern(set_name, GAME_ID, "content", "nome de conjunto")
        if not isinstance(entries, list):
            raise DefinitionError(f"content.{set_name}: esperado uma lista de entradas")
        seen: set[str] = set()
        normalized = []
        for entry in entries:
            entry_id = _check_pattern(_require(entry, "id", f"content.{set_name}"), GAME_ID,
                                      f"content.{set_name}", "id")
            if entry_id in seen:
                raise DefinitionError(f"content.{set_name}: id duplicado {entry_id!r}")
            seen.add(entry_id)
            entry = dict(entry)
            if "bit" in entry and "mask" not in entry:
                entry["mask"] = 1 << parse_int(entry["bit"])
            if "confidence" in entry:
                Confidence.parse(entry["confidence"])
            normalized.append(entry)
        content[set_name] = normalized
    return content


def _expand_achievements(raw_list: list[dict[str, Any]], content: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    expanded = []
    for raw in raw_list:
        if "for_each" not in raw:
            expanded.append(dict(raw))
            continue
        for item in _entries(content, raw["for_each"], f"template {raw.get('id')!r}"):
            if raw.get("where_has") and raw["where_has"] not in item:
                continue
            body = {k: v for k, v in raw.items() if k not in ("for_each", "where_has", "name", "description")}
            entry = _substitute(body, item)
            entry["id"] = f"{raw['id']}.{item['id']}"
            entry["template"] = raw["id"]
            entry["content_confidence"] = item.get("confidence", "verified")
            for text_field in ("name", "description"):
                texts = _localized(raw[text_field], f"template {raw['id']!r}")
                entry[text_field] = {lang: _substitute(text, item, lang) for lang, text in texts.items()}
            expanded.append(entry)
    return expanded


def _parse_binding(raw: dict[str, Any]) -> Binding:
    binding_id = _require(raw, "id", "binding")
    where = f"binding {binding_id!r}"
    _check_keys(raw, "binding", where)
    source = _require(raw, "source", where)
    if source not in SOURCES:
        raise DefinitionError(f"{where}: fonte {source!r} não suportada (use {' ou '.join(SOURCES)})")
    match = raw.get("match", {})
    _check_keys(match, "match", f"{where} match")
    for build_id in match.get("build_ids", []):
        _check_pattern(build_id, HEX16, f"{where} match", "build ID (16 dígitos hex)")
    if source == "memory" and not match.get("build_ids"):
        raise DefinitionError(f"{where}: binding de memória exige match.build_ids")
    if source == "save_json" and not match.get("files"):
        raise DefinitionError(f"{where}: binding save_json exige match.files")
    if source == "save_json" and raw.get("pointers"):
        raise DefinitionError(f"{where}: ponteiros só existem em binding de memória")
    pointers = {}
    for pointer_id, spec in raw.get("pointers", {}).items():
        _check_keys(spec, "ponteiro", f"{where} ponteiro {pointer_id!r}")
        region = _require(spec, "base", f"{where} ponteiro {pointer_id!r}")
        if region not in MEMORY_REGIONS:
            raise DefinitionError(f"{where} ponteiro {pointer_id!r}: região inválida {region!r}")
        chain = tuple(parse_int(o) for o in _require(spec, "chain", f"{where} ponteiro {pointer_id!r}"))
        if not 1 <= len(chain) <= MAX_CHAIN_DEPTH:
            raise DefinitionError(f"{where} ponteiro {pointer_id!r}: cadeia deve ter 1..{MAX_CHAIN_DEPTH} níveis")
        pointers[pointer_id] = Pointer(pointer_id, region, chain)
    raw_variables = dict(_require(raw, "variables", where))
    for name, spec in raw_variables.items():
        _check_keys(spec, "variável do binding", f"{where} variável {name!r}")
        Confidence.parse(spec.get("confidence", "to_discover"))
        if "type" in spec and spec["type"] not in TYPE_SIZES:
            raise DefinitionError(f"{where} variável {name!r}: tipo inválido {spec['type']!r}")
    return Binding(
        id=binding_id,
        label=raw.get("label", binding_id),
        source=source,
        build_ids=tuple(match.get("build_ids", [])),
        files=tuple(match.get("files", [])),
        aliases=dict(raw.get("aliases", {})),
        pointers=pointers,
        active_when=raw.get("active_when"),
        instance_modes=dict(raw.get("instance_modes", {})),
        poll_ms=int(raw.get("poll_ms", 500 if source == "memory" else 2000)),
        raw_variables=raw_variables,
    )


def _implicit_progress(condition: Any) -> dict[str, Any] | None:
    """`{count: e} >= N` com N > 1 vira barra de progresso sem precisar declarar `progress`."""
    if not isinstance(condition, dict) or condition.get("op") != ">=":
        return None
    value = condition.get("value")
    if not (isinstance(value, dict) and "count" in value):
        return None
    try:
        target = parse_int(condition.get("rhs"))
    except (TypeError, ValueError):
        return None
    return {"value": value, "target": target} if target > 1 else None


def parse_definition(raw: dict[str, Any]) -> Definition:
    _check_keys(raw, "definição", "definição")
    schema = _require(raw, "schema_version", "definição")
    if schema != SCHEMA_VERSION:
        raise DefinitionError(f"schema_version {schema} não suportado (esperado {SCHEMA_VERSION})")
    game = _require(raw, "game", "definição")
    _check_keys(game, "game", "game")
    game_id = _check_pattern(_require(game, "id", "game"), GAME_ID, "game", "id (minúsculas, dígitos e _)")
    kind = game.get("kind", "retail")
    if kind not in GAME_KINDS:
        raise DefinitionError(f"game: kind inválido {kind!r} (use {' ou '.join(GAME_KINDS)})")
    title_ids = tuple(_check_pattern(t, HEX16, "game", "title ID (16 dígitos hex)").upper()
                      for t in game.get("title_ids", []))
    if kind == "retail" and not title_ids:
        raise DefinitionError("game: jogo retail exige title_ids")
    content = _normalize_content(raw.get("content", {}))

    variables = {}
    for name, spec in _require(raw, "variables", "definição").items():
        _check_pattern(name, IDENTIFIER, "variables", "nome de variável")
        _check_keys(spec, "variável", f"variável {name!r}")
        var_type = spec.get("type", "u32")
        if var_type not in TYPE_SIZES:
            raise DefinitionError(f"variável {name!r}: tipo inválido {var_type!r}")
        if spec.get("indexed_by") and spec["indexed_by"] not in content:
            raise DefinitionError(f"variável {name!r}: indexed_by {spec['indexed_by']!r} não existe em content")
        variables[name] = {"type": var_type, **spec}

    bindings = {}
    for raw_binding in _require(raw, "bindings", "definição"):
        binding = _parse_binding(raw_binding)
        if binding.id in bindings:
            raise DefinitionError(f"binding duplicado {binding.id!r}")
        for var_name in binding.raw_variables:
            if var_name not in variables:
                raise DefinitionError(f"binding {binding.id!r}: variável não declarada {var_name!r}")
        bindings[binding.id] = binding

    modes = {"default"} | {m for b in bindings.values() for m in b.instance_modes}

    events = {}
    for raw_event in raw.get("events", []):
        event_id = _check_pattern(_require(raw_event, "id", "evento"), IDENTIFIER, "evento", "id")
        _check_keys(raw_event, "evento", f"evento {event_id!r}")
        if event_id in events:
            raise DefinitionError(f"evento {event_id!r}: id duplicado")
        used: list[Confidence] = []
        when = _resolve_content(_require(raw_event, "when", f"evento {event_id!r}"), content, used)
        events[event_id] = Event(event_id, when, min(used, default=Confidence.VERIFIED))

    achievements = []
    seen: set[str] = set()
    raw_achievements = _require(raw, "achievements", "definição")
    for entry in raw_achievements:
        where = f"conquista {entry.get('id')!r}" if isinstance(entry, dict) else "conquista"
        _check_keys(entry, "conquista", where)
        _check_pattern(_require(entry, "id", "conquista"), IDENTIFIER, where, "id")
        if "where_has" in entry and "for_each" not in entry:
            raise DefinitionError(f"{where}: where_has só vale em template (for_each)")
        unknown_modes = set(entry.get("modes", [])) - modes
        if unknown_modes:
            raise DefinitionError(f"{where}: modos desconhecidos {sorted(unknown_modes)} (declarados: {sorted(modes)})")
    expanded = _expand_achievements(raw_achievements, content)
    if len(expanded) > MAX_ACHIEVEMENTS:
        raise DefinitionError(f"definição excede {MAX_ACHIEVEMENTS} conquistas")
    for entry in expanded:
        ach_id = _require(entry, "id", "conquista")
        where = f"conquista {ach_id!r}"
        if ach_id in seen:
            raise DefinitionError(f"{where}: id duplicado")
        seen.add(ach_id)
        rarity = entry.get("rarity", "common")
        if rarity not in RARITIES:
            raise DefinitionError(f"{where}: raridade inválida {rarity!r}")
        used = [Confidence.parse(entry.get("content_confidence", "verified"))]
        progress = _resolve_content(entry.get("progress"), content, [])
        if progress is not None and ("value" not in progress or "target" not in progress):
            raise DefinitionError(f"{where}: progress exige 'value' e 'target'")
        condition = _resolve_content(_require(entry, "condition", where), content, used)
        if progress is None:
            progress = _implicit_progress(condition)
        ach = Achievement(
            id=ach_id,
            name=_localized(_require(entry, "name", where), where),
            description=_localized(_require(entry, "description", where), where),
            xp=int(entry.get("xp", DEFAULT_XP[rarity])),
            rarity=rarity,
            secret=bool(entry.get("secret", False)),
            condition=condition,
            progress=progress,
            modes=tuple(entry["modes"]) if "modes" in entry else None,
            confirm_ticks=int(entry.get("confirm_ticks", 1)),
            template=entry.get("template"),
            content_confidence=min(used),
        )
        _check_achievement(ach, events)
        achievements.append(ach)

    return Definition(
        game_id=game_id,
        name=_localized(_require(game, "name", "game"), "game"),
        kind=kind,
        title_ids=title_ids,
        content=content,
        variables=variables,
        bindings=bindings,
        events=events,
        achievements=achievements,
    )


def _check_achievement(ach: Achievement, events: dict[str, Event]) -> None:
    probe = Context(values={})
    try:
        eval_condition(ach.condition, probe)
        if ach.progress:
            eval_value(ach.progress["value"], probe)
            parse_int(ach.progress["target"])
    except (ExprError, KeyError, TypeError) as exc:
        raise DefinitionError(f"conquista {ach.id!r}: {exc}") from exc
    refs = collect_references(ach.condition)
    unknown = refs.events - set(events)
    if unknown:
        raise DefinitionError(f"conquista {ach.id!r}: eventos desconhecidos {sorted(unknown)}")


def load_definition(path: Path) -> Definition:
    try:
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except json.JSONDecodeError as exc:
        raise DefinitionError(f"JSON inválido na linha {exc.lineno}, coluna {exc.colno}: {exc.msg}") from exc
    except OSError as exc:
        raise DefinitionError(f"não foi possível ler {path}: {exc.strerror}") from exc
    return parse_definition(raw)


# --------------------------------------------------------------------------
# indexação


def _instances_for(name: str, decl: dict[str, Any], spec: dict[str, Any], binding: Binding,
                   content: dict[str, list[dict[str, Any]]]) -> list[VarInstance]:
    where = f"binding {binding.id!r} variável {name!r}"
    confidence = Confidence.parse(spec.get("confidence", "to_discover"))
    note = spec.get("note")
    var_type = spec.get("type", decl["type"])

    def make(instance_name: str, offset: int | None, path: str | None, conf: Confidence) -> VarInstance:
        if conf is Confidence.TO_DISCOVER:
            return VarInstance(instance_name, var_type, conf, note=note)
        if binding.source == "memory":
            region = spec.get("base")
            pointer = spec.get("from")
            if (region is None) == (pointer is None):
                raise DefinitionError(f"{where}: use exatamente um entre 'base' e 'from'")
            if region is not None and region not in MEMORY_REGIONS:
                raise DefinitionError(f"{where}: região inválida {region!r}")
            if pointer is not None and pointer not in binding.pointers:
                raise DefinitionError(f"{where}: ponteiro desconhecido {pointer!r}")
            if offset is None:
                raise DefinitionError(f"{where}: 'offset' obrigatório")
            return VarInstance(instance_name, var_type, conf, region=region, pointer=pointer, offset=offset, note=note)
        if path is None:
            raise DefinitionError(f"{where}: 'path' obrigatório")
        return VarInstance(instance_name, var_type, conf, path=path, note=note)

    indexed_by = decl.get("indexed_by")
    if not indexed_by:
        offset = parse_int(spec["offset"]) if "offset" in spec else None
        return [make(name, offset, spec.get("path"), confidence)]

    instances = []
    key = spec.get("index_key", "index")
    stride = parse_int(spec.get("stride", 0))
    for entry in content[indexed_by]:
        instance_name = f"{name}[{entry['id']}]"
        if key not in entry:
            instances.append(VarInstance(instance_name, var_type, Confidence.TO_DISCOVER,
                                         note=f"entrada sem '{key}' em content.{indexed_by}"))
            continue
        index = parse_int(entry[key])
        entry_conf = min(confidence, Confidence.parse(entry.get("confidence", "verified")))
        offset = parse_int(spec["offset"]) + stride * index if "offset" in spec else None
        path = _substitute(spec["path"], {**entry, "key": index}) if "path" in spec else None
        instances.append(make(instance_name, offset, path, entry_conf))
    return instances


def _plan_reads(instances: dict[str, VarInstance], gap: int = 0x40) -> list[ReadBlock]:
    """Agrupa variáveis próximas sob a mesma âncora em leituras contíguas."""
    groups: dict[str, list[VarInstance]] = {}
    for inst in instances.values():
        if inst.offset is None:
            continue
        anchor = f"ptr:{inst.pointer}" if inst.pointer else f"region:{inst.region}"
        groups.setdefault(anchor, []).append(inst)

    blocks = []
    for anchor, members in sorted(groups.items()):
        members.sort(key=lambda i: i.offset)
        current: list[VarInstance] = []
        start = end = 0
        for inst in members:
            inst_end = inst.offset + inst.size
            if current and (inst.offset - end > gap or inst_end - start > MAX_BLOCK):
                blocks.append(ReadBlock(anchor, start, end - start, tuple(i.name for i in current)))
                current = []
            if not current:
                start = inst.offset
                end = inst_end
            current.append(inst)
            end = max(end, inst_end)
        if current:
            blocks.append(ReadBlock(anchor, start, end - start, tuple(i.name for i in current)))
    return blocks


def build_index(definition: Definition, binding: Binding) -> Index:
    instances: dict[str, VarInstance] = {}
    for name, spec in binding.raw_variables.items():
        for inst in _instances_for(name, definition.variables[name], spec, binding, definition.content):
            instances[inst.name] = inst

    def confidence_of(var_names: set[str], blockers: list[str]) -> Readiness:
        level = Readiness.LIVE
        for var in sorted(var_names):
            inst = instances.get(var)
            if inst is None:
                blockers.append(f"{var}: não declarada neste binding")
                level = min(level, Readiness.UNSUPPORTED)
            elif inst.confidence is Confidence.TO_DISCOVER:
                blockers.append(f"{var}: endereço a descobrir")
                level = min(level, Readiness.PENDING)
            elif inst.confidence is Confidence.ASSUMED:
                blockers.append(f"{var}: endereço presumido (ensaio)")
                level = min(level, Readiness.REHEARSAL)
        return level

    guard_vars = collect_references(binding.active_when).variables if binding.active_when else set()
    readiness: dict[str, Readiness] = {}
    blockers: dict[str, list[str]] = {}
    for ach in definition.achievements:
        refs = collect_references(ach.condition)
        var_names = set(refs.variables) | guard_vars
        for event_id in refs.events:
            var_names |= collect_references(definition.events[event_id].when).variables
        reasons: list[str] = []
        level = confidence_of(var_names, reasons)
        content_levels = [ach.content_confidence] + [definition.events[e].content_confidence for e in refs.events]
        weakest = min(content_levels)
        if weakest is Confidence.TO_DISCOVER:
            reasons.append("valor de conteúdo a descobrir")
            level = min(level, Readiness.PENDING)
        elif weakest is Confidence.ASSUMED:
            reasons.append("valor de conteúdo presumido (ensaio)")
            level = min(level, Readiness.REHEARSAL)
        readiness[ach.id] = level
        blockers[ach.id] = reasons

    plan = _plan_reads(instances) if binding.source == "memory" else []
    return Index(definition, binding, instances, dict(definition.events), list(definition.achievements),
                 readiness, blockers, plan)
