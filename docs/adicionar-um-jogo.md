# Como adicionar um jogo

Adicionar um jogo é **adicionar um arquivo**: `games/<id>.json`, na estrutura padrão. Não há código, registro manual nem teste novo a escrever. O catálogo descobre o arquivo sozinho, e a suíte de testes valida qualquer `games/*.json` automaticamente.

A estrutura completa está em [modelo-de-definicao.md](modelo-de-definicao.md). O schema para o editor é [`schema/game-definition.schema.json`](../schema/game-definition.schema.json); com a linha `"$schema"` no topo do arquivo, o VS Code ou o Cursor autocompletam os campos e sublinham erros.

## 1. Criar o esqueleto

```bash
# jogo retail (lido da memória)
python3 tools/sa.py new super_mario_odyssey --name "Super Mario Odyssey" \
  --title-id 0100000000010000 --build-id <BUILD_ID_DO_SEU_CONSOLE>

# homebrew/port que grava save em JSON
python3 tools/sa.py new two_ship_two_harkinian --name "2 Ship 2 Harkinian" --save-file Save/file1.sav
```

O comando cria `games/<id>.json` com um binding, uma variável `to_discover` e uma conquista de exemplo. O arquivo já é válido; o resto é edição.

Regras que o validador cobra:

| Regra | Exemplo |
|---|---|
| Nome do arquivo = `game.id` (minúsculas, dígitos e `_`) | `games/super_mario_odyssey.json` ↔ `"id": "super_mario_odyssey"` |
| Retail exige `title_ids`; um Title ID pertence a um único arquivo | `"title_ids": ["0100000000010000"]` |
| Binding de memória exige `match.build_ids` (16 dígitos hex) | `"build_ids": ["3CA12DFAAF9C82DA"]` |
| Binding `save_json` exige `match.files` | `"files": ["Save/file1.sav"]` |
| Nenhuma chave fora da estrutura padrão | `"condtion"` vira erro, com a lista das chaves permitidas |
| Toda variável usada em binding, condição ou evento precisa estar declarada | `variables` → `bindings[].variables` |
| `modes` de conquista só com modos declarados em `instance_modes` (ou `default`) | |

## 2. Preencher, de cima para baixo

1. **`content`**: liste o que existe no jogo (luas, reinos, copas, chefes) com a chave que o jogo usa: `slot`/`index` para posição numa tabela, `bit` para bitfield, `value` para código de item. Itens deduzidos levam `"confidence": "assumed"`.
2. **`variables`**: o estado que as conquistas precisam (`moons.total`, `kingdom.moons` com `indexed_by: "kingdoms"`). Nada de endereços aqui.
3. **`bindings`**: um por build. Para cada variável, `base` + `offset` (endereço estático em `main`), ou `from` + `offset` (ponteiro declarado em `pointers`), sempre com `confidence` e `note` (de onde veio o endereço). Endereço que você ainda não achou fica `"confidence": "to_discover"` com a dica de busca em `note`.
4. **`events`**: momentos que valem contar ("pegou uma lua"), como borda de subida.
5. **`achievements`**: condições sobre variáveis e contadores. Use `for_each` para gerar uma por item do conteúdo.

Pode publicar o arquivo incompleto: conquistas com endereço `to_discover` não são avaliadas, e as `assumed` só rodam em ensaio. Nada desbloqueia errado.

## 3. Conferir

```bash
python3 tools/sa.py validate                                   # todos os games/*.json
python3 tools/sa.py index super_mario_odyssey                  # endereços, plano de leitura, prontidão
python3 tools/sa.py detect 0100000000010000 <BUILD_ID>         # o que o console escolheria
python3 tools/sa.py list                                       # visão geral do catálogo
python3 -m unittest discover -s tools/tests -t tools/tests     # inclui o novo arquivo automaticamente
```

Para testar sem console, escreva um trace em `examples/traces/` (formato na seção 8 do modelo) e rode `python3 tools/sa.py replay super_mario_odyssey examples/traces/<trace>.json --verbose`.

### Ícones (opcional)

Coloque PNGs em `assets/icons/<id>/`, com o nome do `id` da conquista ou do seu `template` (um ícone cobre o template inteiro). Qualquer tamanho serve; o `build` reduz para 50×50. Sem ícone, a conquista usa o troféu de `assets/icons/common/`.

## 4. Nova versão de um jogo já existente

Não crie outro arquivo. Adicione um binding em `bindings` com o novo build ID. Conteúdo, variáveis, eventos e conquistas são reaproveitados. Se os endereços não mudaram entre versões, basta incluir o build ID em `match.build_ids` do binding existente, como em `zelda_links_awakening.json`.
