# Switch Achievements

Plataforma de conquistas independente para Nintendo Switch com Atmosphère. Cada jogo é descrito por **um JSON** (conteúdo, variáveis, endereços por build e conquistas). O motor indexa esse JSON em um plano de leitura de memória via `dmnt:cht` (ou de leitura do save, para ports homebrew), registra desbloqueios no SD e exibe notificações por meio do overlay Ultrahand/libtesla. Não há código específico por jogo.

## Status

- Estudo de viabilidade: [`docs/estudo-viabilidade.md`](docs/estudo-viabilidade.md)
- Modelo de definição (schema v2): [`docs/modelo-de-definicao.md`](docs/modelo-de-definicao.md)
- Jogos da v1:

| Jogo | Fonte | Conquistas | Ativas / ensaio / a descobrir |
|---|---|---|---|
| [Mario Kart 8 Deluxe](games/mario_kart_8_deluxe/definition.json) | memória | 35 | 6 / 1 / 28 |
| [Link's Awakening](games/zelda_links_awakening/definition.json) | memória | 45 | 24 / 12 / 9 |
| [Ship of Harkinian (OoT)](games/ship_of_harkinian/definition.json) | save JSON ([detalhes](docs/jogos/ship-of-harkinian.md)) | 34 | 34 / 0 / 0 |

"Ensaio" são conquistas com endereço ou valor presumido: elas são avaliadas, mas não desbloqueiam até a confirmação no console. "A descobrir" são as que aguardam um endereço ainda não encontrado.

O avaliador de referência em `tools/` (Python 3.10+, sem dependências) define a semântica que o sysmodule C++ vai seguir.

## Uso no PC

```bash
# índice: variáveis por build, ponteiros, plano de leitura e prontidão das conquistas
python3 tools/sa.py index games/mario_kart_8_deluxe/definition.json

# reproduz um trace de memória simulada (MK8 e LA)
python3 tools/sa.py replay games/mario_kart_8_deluxe/definition.json examples/traces/mk8_corrida.json --verbose
python3 tools/sa.py replay games/zelda_links_awakening/definition.json examples/traces/la_progresso.json

# saves do Ship of Harkinian (copie sdmc:/switch/soh/Save/ com o jogo fechado)
python3 tools/sa.py save games/ship_of_harkinian/definition.json --save-dir examples/soh/Save \
  --state estado.json --notify-dir notificacoes/
```

Opções comuns: `--state` (persiste desbloqueios, contadores e XP), `--notify-dir`, `--reveal-secrets`, `--lang en`, `--binding`/`--build` (no `index`) e `--watch` (no `save`).

Os arquivos em `notificacoes/` usam o formato `.notify` do Ultrahand. Copiados para `sdmc:/config/ultrahand/notifications/`, eles aparecem como toast no Switch.

## Testes

```bash
python3 -m unittest discover -s tools/tests -t tools/tests
```

## Requisitos previstos no console

- Atmosphère (recomendado: emuMMC, modo offline)
- Ultrahand Overlay ≥ 2.3 com nx-ovlloader
- EdiZon ou Breeze para confirmar build IDs e descobrir endereços
- devkitPro (`switch-dev`) para compilar o sysmodule e o overlay
