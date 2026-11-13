# Overlay Switch Achievements

Tela do console, feita com [libultrahand](https://github.com/ppkantorski/libultrahand) (submódulo em `lib/`). Ela só lê o que o PC (e, depois, o sysmodule) publica em `sdmc:/config/switch-achievements/`: `profile.json`, `progress/<jogo>.json` e `icons/<chave>.rgba`. O formato está em `tools/sa_core/progress.py`.

## Compilar

```bash
git submodule update --init --depth 1
docker run --rm -u $(id -u):$(id -g) -v "$PWD":/src -w /src devkitpro/devkita64:latest make
```

Rode o comando dentro de `overlay/`. Com devkitPro instalado localmente, basta `make`. O resultado é `overlay/switch-achievements.ovl`, que `python3 tools/sa.py build` e `device install` levam para `sdmc:/switch/.overlays/`.
