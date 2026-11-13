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

## Teste no Switch pela rede local

O sysmodule em C++ ainda não existe. Com o sys-ftpd aberto, ou com o FTP do DBI mostrando o SD inteiro (não a pasta de instalação), o PC fala com o console na rede local. Copie `device.local.json.example` para `device.local.json` e preencha o IP, a porta e o login. Esse arquivo fica só na máquina.

```bash
python3 tools/sa.py device probe     # confere o SD e as pastas do Ultrahand e do SoH
python3 tools/sa.py device install   # envia overlay, ícones, definições e som (dist/sd/)
python3 tools/sa.py device notify    # toast de teste, com o ícone de troféu
python3 tools/sa.py device sync      # avalia os saves, publica o progresso e notifica o que for novo
```

`sync` guarda o estado no próprio SD (`state.json`), então só notifica desbloqueios novos; o primeiro `sync` notifica tudo o que o save já cumpriu. Rode com o SoH fechado. `--no-notify` só atualiza a tela.

`install` nunca mexe no estado nem no progresso. O som de conquista substitui o som **global** de notificação do Ultrahand: o original fica em `sdmc:/config/switch-achievements/backup/` e volta com `device restore-sound`. Use `install --no-sound` para manter o original. O Ultrahand carrega sons ao abrir; feche e abra o menu (ou reinicie) depois de instalar.

Sem rede, `python3 tools/sa.py build` monta a mesma árvore em `dist/sd/` para copiar ao cartão.

## No console

O overlay **Switch Achievements** aparece no menu do Ultrahand. A tela inicial mostra nível, XP e os jogos com `concluídas/total`; ao abrir um jogo, as conquistas aparecem separadas em **Concluídas** e **Bloqueadas**, com ícone (cinza enquanto bloqueada), XP, raridade e barra de progresso quando a conquista tem contador. Secretas bloqueadas ficam escondidas.

O toast de cada conquista leva o ícone dela. O Ultrahand acha o ícone pelo nome do arquivo `.notify` (`SwitchAchievements-<jogo>.<ícone>-<n>.notify` → `config/ultrahand/assets/notifications/SwitchAchievements-<jogo>.<ícone>.rgba`).

## Estrutura

| No repositório | Para quê |
| --- | --- |
| `games/<id>.json` | definição de cada jogo |
| `assets/icons/<id>/<conquista ou template>.png` | ícones 50×50; sem ícone, usa `assets/icons/common/trophy.png` |
| `assets/sounds/achievement.wav` | som da conquista (PCM 16 bits, 48 kHz) |
| `overlay/` | tela do console (C++, libultrahand como submódulo) |
| `tools/` | CLI e avaliador de referência; caminhos do SD em `tools/sa_core/layout.py` |

| No SD | Quem escreve |
| --- | --- |
| `switch/.overlays/switch-achievements.ovl` | `install` |
| `config/switch-achievements/games/`, `icons/`, `sounds/` | `install` |
| `config/switch-achievements/state.json`, `profile.json`, `progress/<jogo>.json` | `sync` (depois, o sysmodule) |
| `config/ultrahand/assets/notifications/SwitchAchievements-*.rgba` | `install` |
| `config/ultrahand/sounds/notification.wav` | `install` (original em `backup/`) |

Compilar o overlay: [`overlay/README.md`](overlay/README.md).

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
