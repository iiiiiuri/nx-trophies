# Switch Achievements

Plataforma de conquistas independente para Nintendo Switch com Atmosphère. Cada jogo é descrito por **um JSON** (conteúdo, variáveis, endereços por build e conquistas). O motor indexa esse JSON em um plano de leitura de memória via `dmnt:cht` (ou de leitura do save, para ports homebrew), registra desbloqueios no SD e exibe notificações por meio do overlay Ultrahand/libtesla. Não há código específico por jogo.

## Adicionar um jogo

O que o repositório mantém são os arquivos `games/*.json`. Para suportar um jogo novo, adicione `games/<id>.json` na estrutura padrão; o catálogo o descobre sozinho e a suíte de testes o valida automaticamente.

```bash
python3 tools/sa.py new super_mario_odyssey --name "Super Mario Odyssey" --title-id 0100000000010000 --build-id <BUILD_ID>
python3 tools/sa.py validate
```

Guia completo: [`docs/adicionar-um-jogo.md`](docs/adicionar-um-jogo.md). Estrutura: [`docs/modelo-de-definicao.md`](docs/modelo-de-definicao.md). Schema para o editor: [`schema/game-definition.schema.json`](schema/game-definition.schema.json).

## Status

- Estudo de viabilidade: [`docs/estudo-viabilidade.md`](docs/estudo-viabilidade.md)
- Jogos da v1:

| Jogo | Fonte | Conquistas | Ativas / ensaio / a descobrir |
|---|---|---|---|
| [Mario Kart 8 Deluxe](games/mario_kart_8_deluxe.json) | memória | 35 | 6 / 1 / 28 |
| [Link's Awakening](games/zelda_links_awakening.json) | memória | 45 | 24 / 12 / 9 |
| [Ship of Harkinian (OoT)](games/ship_of_harkinian.json) | save JSON ([detalhes](docs/jogos/ship-of-harkinian.md)) | 34 | 34 / 0 / 0 |

"Ensaio" são conquistas com endereço ou valor presumido: elas são avaliadas, mas não desbloqueiam até a confirmação no console. "A descobrir" são as que aguardam um endereço ainda não encontrado.

O avaliador de referência em `tools/` (Python 3.10+, sem dependências) define a semântica que o sysmodule C++ vai seguir.

## Uso no PC

Os comandos aceitam o id do jogo (`mario_kart_8_deluxe`) ou o caminho do `.json`.

```bash
# catálogo: jogos, title IDs, bindings e prontidão
python3 tools/sa.py list

# qual jogo e binding o console usaria para um title ID + build ID
python3 tools/sa.py detect 0100152000022000 FE941ED5BA14BE5D

# índice: variáveis por build, ponteiros, plano de leitura e prontidão das conquistas
python3 tools/sa.py index mario_kart_8_deluxe

# reproduz um trace de memória simulada (MK8 e LA)
python3 tools/sa.py replay mario_kart_8_deluxe examples/traces/mk8_corrida.json --verbose
python3 tools/sa.py replay zelda_links_awakening examples/traces/la_progresso.json

# saves do Ship of Harkinian (copie sdmc:/switch/soh/Save/ com o jogo fechado)
python3 tools/sa.py save ship_of_harkinian --save-dir examples/soh/Save \
  --state estado.json --notify-dir notificacoes/
```

Opções comuns: `--state` (persiste desbloqueios, contadores e XP), `--notify-dir`, `--reveal-secrets`, `--lang en`, `--binding`/`--build` (no `index`) e `--watch` (no `save`).

Os arquivos em `notificacoes/` usam o formato `.notify` do Ultrahand. Copiados para `sdmc:/config/ultrahand/notifications/`, eles aparecem como toast no Switch.

## Testes

```bash
python3 -m unittest discover -s tools/tests -t tools/tests
```

A verificação contra o JSON Schema roda quando o pacote `jsonschema` está instalado (`pip install jsonschema`); sem ele, esse teste é pulado e o resto da suíte continua sem dependências.

## Requisitos previstos no console

- Atmosphère (recomendado: emuMMC, modo offline)
- Ultrahand Overlay ≥ 2.3 com nx-ovlloader
- EdiZon ou Breeze para confirmar build IDs e descobrir endereços
- devkitPro (`switch-dev`) para compilar o sysmodule e o overlay
