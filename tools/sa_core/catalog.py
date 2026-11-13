"""Catálogo de jogos: todo `games/*.json` é um jogo, sem registro manual.

Adicionar um jogo = adicionar `games/<game.id>.json` na estrutura padrão.
O catálogo valida cada arquivo (estrutura, índice de todos os bindings) e o
conjunto (nome do arquivo = id, title IDs sem conflito) e resolve qual jogo
e qual binding usar a partir do title ID e build ID do processo em execução.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .definition import SCHEMA_VERSION, Binding, Definition, DefinitionError, build_index, load_definition

REPO_DIR = Path(__file__).resolve().parents[2]
GAMES_DIR = REPO_DIR / "games"


@dataclass(frozen=True)
class Problem:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path.name}: {self.message}"


@dataclass
class Catalog:
    games: dict[str, Definition]
    paths: dict[str, Path]
    problems: list[Problem]

    def by_title_id(self, title_id: str) -> Definition | None:
        wanted = title_id.upper()
        for definition in self.games.values():
            if wanted in definition.title_ids:
                return definition
        return None

    def detect(self, title_id: str, build_id: str) -> tuple[Definition | None, Binding | None]:
        definition = self.by_title_id(title_id)
        if definition is None:
            return None, None
        return definition, definition.binding_for_build(build_id)


def game_files(directory: Path = GAMES_DIR) -> list[Path]:
    return sorted(p for p in directory.glob("*.json") if p.is_file())


def check_definition(path: Path) -> tuple[Definition | None, list[Problem]]:
    """Carrega um arquivo e indexa todos os bindings: erros que só aparecem no console aparecem aqui."""
    try:
        definition = load_definition(path)
    except DefinitionError as exc:
        return None, [Problem(path, str(exc))]
    problems = []
    if definition.game_id != path.stem:
        problems.append(Problem(path, f"o arquivo deve se chamar {definition.game_id}.json (game.id)"))
    if not definition.bindings:
        problems.append(Problem(path, "nenhum binding declarado"))
    for binding in definition.bindings.values():
        try:
            build_index(definition, binding)
        except DefinitionError as exc:
            problems.append(Problem(path, str(exc)))
    return definition, problems


def load_catalog(directory: Path = GAMES_DIR) -> Catalog:
    games: dict[str, Definition] = {}
    paths: dict[str, Path] = {}
    problems: list[Problem] = []
    owners: dict[str, str] = {}
    for path in game_files(directory):
        definition, found = check_definition(path)
        problems += found
        if definition is None or found:
            continue
        if definition.game_id in games:
            problems.append(Problem(path, f"game.id {definition.game_id!r} repetido"))
            continue
        clash = [t for t in definition.title_ids if t in owners]
        if clash:
            problems.append(Problem(path, f"title ID {clash[0]} já pertence a {owners[clash[0]]}"))
            continue
        for title_id in definition.title_ids:
            owners[title_id] = definition.game_id
        games[definition.game_id] = definition
        paths[definition.game_id] = path
    return Catalog(games, paths, problems)


def new_definition(game_id: str, name: str, *, title_id: str | None = None, build_id: str | None = None,
                   save_file: str | None = None) -> dict[str, Any]:
    """Esqueleto válido na estrutura padrão: um binding, uma variável a descobrir, uma conquista."""
    homebrew = save_file is not None
    game: dict[str, Any] = {"id": game_id, "name": {"pt-BR": name, "en": name},
                            "kind": "homebrew" if homebrew else "retail"}
    if title_id:
        game["title_ids"] = [title_id.upper()]
    if homebrew:
        binding: dict[str, Any] = {
            "id": "save", "label": "Save JSON", "source": "save_json",
            "match": {"files": [save_file]},
            "variables": {"progress.value": {"confidence": "to_discover", "path": "caminho.no.save",
                                             "note": "caminho do campo dentro do JSON do save"}},
        }
    else:
        build = (build_id or "0000000000000000").upper()
        binding = {
            "id": f"build_{build}", "label": f"Build {build}", "source": "memory",
            "match": {"build_ids": [build]},
            "variables": {"progress.value": {"confidence": "to_discover",
                                             "note": "buscar no Breeze/EdiZon; registrar base/offset ou ponteiro"}},
        }
    return {
        "$schema": "../schema/game-definition.schema.json",
        "schema_version": SCHEMA_VERSION,
        "game": game,
        "content": {},
        "variables": {"progress.value": {"type": "u32", "description": "Exemplo: troque pelo estado real do jogo."}},
        "bindings": [binding],
        "events": [],
        "achievements": [{
            "id": "first_step",
            "name": {"pt-BR": "Primeiro Passo", "en": "First Step"},
            "description": {"pt-BR": "Exemplo: troque pela primeira conquista real.", "en": "Example achievement."},
            "condition": {"value": "progress.value", "op": ">=", "rhs": 1},
        }],
    }


def resolve_game_path(arg: str | Path, directory: Path = GAMES_DIR) -> Path:
    """Aceita o caminho de um arquivo ou só o id do jogo (`mario_kart_8_deluxe`)."""
    path = Path(arg)
    if path.suffix == ".json" or path.exists():
        return path
    return directory / f"{arg}.json"
