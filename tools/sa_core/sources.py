"""Fontes que transformam o mundo real em snapshots de variáveis.

MemorySource executa o plano de leitura do índice sobre um `MemoryReader`.
No console o reader é o `dmnt:cht` (dmntchtGetCheatProcessMetadata para as
regiões, dmntchtReadCheatProcessMemory para os blocos); aqui há um processo
simulado (`FakeProcess`) usado em testes e replays de traces.
"""

from __future__ import annotations

import json
import re
import struct
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .definition import Index, Pointer
from .expr import MISSING, parse_int

_FORMATS = {"u8": "<B", "s8": "<b", "u16": "<H", "s16": "<h", "u32": "<I", "s32": "<i",
            "u64": "<Q", "s64": "<q", "f32": "<f", "f64": "<d"}
_PATH_TOKEN = re.compile(r"([^.\[\]]+)|\[(0x[0-9a-fA-F]+|\d+)\]")


class MemoryReadError(RuntimeError):
    pass


@dataclass(frozen=True)
class Snapshot:
    label: str
    values: dict[str, Any]


class MemoryReader(Protocol):
    def regions(self) -> dict[str, tuple[int, int]]: ...
    def read(self, address: int, size: int) -> bytes: ...


def decode(var_type: str, data: bytes) -> int | float:
    return struct.unpack(_FORMATS[var_type], data)[0]


class FakeProcess:
    """Processo simulado: regiões nomeadas + memória esparsa (bytes não escritos valem 0)."""

    def __init__(self, regions: dict[str, tuple[int, int]]):
        self._regions = dict(regions)
        self._bytes: dict[int, int] = {}

    def regions(self) -> dict[str, tuple[int, int]]:
        return dict(self._regions)

    def _mapped(self, address: int, size: int) -> bool:
        return any(base <= address and address + size <= base + length for base, length in self._regions.values())

    def read(self, address: int, size: int) -> bytes:
        if not self._mapped(address, size):
            raise MemoryReadError(f"leitura fora das regiões mapeadas: 0x{address:X}+{size}")
        return bytes(self._bytes.get(address + i, 0) for i in range(size))

    def write(self, address: int, data: bytes) -> None:
        if not self._mapped(address, len(data)):
            raise MemoryReadError(f"escrita fora das regiões mapeadas: 0x{address:X}")
        for i, byte in enumerate(data):
            self._bytes[address + i] = byte

    def write_value(self, address: int, var_type: str, value: int | float) -> None:
        self.write(address, struct.pack(_FORMATS[var_type], value))

    def address(self, expr: str) -> int:
        """Aceita '0x1234' ou 'main+0x1234'."""
        if "+" in expr:
            region, offset = expr.split("+", 1)
            return self._regions[region.strip()][0] + parse_int(offset.strip())
        return parse_int(expr)


class MemorySource:
    def __init__(self, index: Index, reader: MemoryReader):
        self.index = index
        self.reader = reader
        self.read_calls = 0

    def _in_regions(self, address: int, size: int, regions: dict[str, tuple[int, int]]) -> bool:
        return any(base <= address and address + size <= base + length for base, length in regions.values())

    def _resolve(self, pointer: Pointer, regions: dict[str, tuple[int, int]]) -> int | None:
        width = self.index.binding.pointer_width
        address = regions[pointer.region][0]
        for offset in pointer.chain:
            slot = address + offset
            if not self._in_regions(slot, width, regions):
                return None
            try:
                self.read_calls += 1
                address = decode("u64" if width == 8 else "u32", self.reader.read(slot, width))
            except MemoryReadError:
                return None
            if address == 0:
                return None
        return address

    def read(self) -> list[Snapshot]:
        regions = self.reader.regions()
        anchors: dict[str, int | None] = {f"region:{name}": base for name, (base, _) in regions.items()}
        for pointer in self.index.binding.pointers.values():
            anchors[f"ptr:{pointer.id}"] = self._resolve(pointer, regions)

        values: dict[str, Any] = {}
        for block in self.index.read_plan:
            base = anchors.get(block.anchor)
            data = None
            if base is not None and self._in_regions(base + block.offset, block.size, regions):
                try:
                    self.read_calls += 1
                    data = self.reader.read(base + block.offset, block.size)
                except MemoryReadError:
                    data = None
            for name in block.variables:
                inst = self.index.instances[name]
                if data is None:
                    values[name] = MISSING
                    continue
                start = inst.offset - block.offset
                values[name] = decode(inst.type, data[start:start + inst.size])
        return [Snapshot("memória", values)]


def _split_path(path: str) -> list[str | int]:
    return [key if key else int(index, 0) for key, index in _PATH_TOKEN.findall(path)]


def resolve_path(document: Any, path: str, aliases: dict[str, str]) -> Any:
    parts = _split_path(path)
    if parts and isinstance(parts[0], str) and parts[0] in aliases:
        parts = _split_path(aliases[parts[0]]) + parts[1:]
    node = document
    for part in parts:
        if part == "length" and isinstance(node, list):
            node = len(node)
        elif isinstance(part, int) and isinstance(node, list) and 0 <= part < len(node):
            node = node[part]
        elif isinstance(part, str) and isinstance(node, dict) and part in node:
            node = node[part]
        else:
            return MISSING
    return node


def snapshot_from_document(index: Index, label: str, document: Any) -> Snapshot:
    values = {}
    for inst in index.instances.values():
        if inst.path is not None:
            values[inst.name] = resolve_path(document, inst.path, index.binding.aliases)
    return Snapshot(label, values)


def read_json_file(path: Path, retries: int = 3, delay: float = 0.3) -> Any:
    """Lê um JSON tolerando escrita em andamento (vários jogos gravam o arquivo no lugar)."""
    for attempt in range(retries):
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except FileNotFoundError:
            return MISSING
        except (json.JSONDecodeError, UnicodeDecodeError):
            if attempt + 1 < retries:
                time.sleep(delay)
    return MISSING


class FileSource:
    def __init__(self, index: Index, paths: list[Path]):
        self.index = index
        self.paths = paths

    def read(self) -> list[Snapshot]:
        snapshots = []
        for path in self.paths:
            document = read_json_file(path)
            if document is not MISSING:
                snapshots.append(snapshot_from_document(self.index, path.name, document))
        return snapshots
