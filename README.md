# Switch Achievements

Plataforma de conquistas independente para Nintendo Switch com Atmosphère: um sysmodule avalia condições declaradas em JSON (saves legíveis, tempo de jogo, memória do jogo via `dmnt:cht`), registra desbloqueios no SD e exibe notificações sobre o jogo por meio de um overlay (Ultrahand/libtesla).

## Status

- Estudo de viabilidade: [`docs/estudo-viabilidade.md`](docs/estudo-viabilidade.md)
- Jogo-piloto: **Ship of Harkinian** (Ocarina of Time). Modelo em [`docs/jogos/ship-of-harkinian.md`](docs/jogos/ship-of-harkinian.md), pack com 27 conquistas em [`packs/ship_of_harkinian/pack.json`](packs/ship_of_harkinian/pack.json)
- Avaliador de referência (Python, sem dependências) em `tools/`: define a semântica que o motor C++ do console vai seguir

## Testar o pack no PC

Requer Python 3.10+.

```bash
# com os saves de exemplo
python3 tools/sa_eval.py packs/ship_of_harkinian/pack.json --save-dir examples/soh/Save

# com o seu save real (copie sdmc:/switch/soh/Save/ com o jogo fechado)
python3 tools/sa_eval.py packs/ship_of_harkinian/pack.json --save-dir /caminho/Save \
  --state estado.json --notify-dir notificacoes/
```

Opções: `--watch` (reavalia quando o save muda), `--verbose` (campos ausentes), `--reveal-secrets`, `--lang en`.

Os arquivos em `notificacoes/` usam o formato `.notify` do Ultrahand. Copiados para `sdmc:/config/ultrahand/notifications/`, eles aparecem como toast no Switch.

## Testes

```bash
python3 -m unittest discover -s tools/tests -t tools/tests
```

## Requisitos previstos no console

- Atmosphère (recomendado: emuMMC, modo offline)
- Ultrahand Overlay ≥ 2.3 com nx-ovlloader
- devkitPro (`switch-dev`) para compilar o sysmodule e o overlay
