# Switch Achievements

Plataforma de conquistas independente para Nintendo Switch com Atmosphère: um sysmodule avalia condições declaradas em JSON (tempo de jogo, memória do jogo via `dmnt:cht`), registra desbloqueios no SD e exibe notificações sobre o jogo por meio de um overlay (Ultrahand/libtesla).

## Status

Fase de estudo. Ainda não há código; a arquitetura, os riscos e o MVP estão em [`docs/estudo-viabilidade.md`](docs/estudo-viabilidade.md).

## Requisitos previstos

- Console com Atmosphère (recomendado: emuMMC, modo offline)
- Ultrahand Overlay ≥ 2.3 com nx-ovlloader
- devkitPro (`switch-dev`) para compilar
