# Ship of Harkinian (Ocarina of Time): modelo de conquistas

> Um dos três jogos da v1, ao lado de Mario Kart 8 Deluxe e Link's Awakening. Definição: [`games/ship_of_harkinian/definition.json`](../../games/ship_of_harkinian/definition.json). O formato é o mesmo dos jogos retail ([modelo de definição](../modelo-de-definicao.md)); só muda o **binding**, que aqui lê o save em vez da memória.

## 1. Por que o SoH é um bom piloto

O Ship of Harkinian (SoH) é um port nativo de Ocarina of Time, com **código aberto** ([HarbourMasters/Shipwright](https://github.com/HarbourMasters/Shipwright)). Isso muda a estratégia descrita no estudo de viabilidade:

| Rota | Situação no SoH |
|---|---|
| Leitura de memória via `dmnt:cht` | **Fraca.** O SoH é um homebrew (`soh.nro`), não um título retail. O `dmnt` só se anexa a homebrew via `ForceOpenCheatProcess` e quando ele roda como aplicação (title takeover, segurando R ao abrir um jogo). Mesmo assim, o "módulo principal" visto é o `hbloader`, e não o `soh.nro` ([`dmnt_cheat_api.cpp`](https://github.com/Atmosphere-NX/Atmosphere/blob/master/stratosphere/dmnt/source/cheat/impl/dmnt_cheat_api.cpp): *"Only accept one (which means we're attaching to HBL)"*). Não há build ID confiável, e os endereços teriam que ser achados por varredura. |
| **Arquivo de save (JSON)** | **Forte. É a rota escolhida.** O SoH grava `Save/fileN.sav` como JSON legível, com o estado do jogo **e** uma seção de estatísticas (`sohStats`): timestamps de chefes derrotados, contadores de inimigos, rolamentos, potes, tempo de jogo etc. Não exige engenharia reversa: os campos vêm do código-fonte. |
| Integração nativa (fork do SoH) | **Futuro.** O SoH tem um barramento de eventos (`GameInteractor`, com hooks como `OnLoadGame` e `OnGameFrameUpdate`) e um sistema de toasts próprio (`Notification::Emit`). Um fork poderia emitir eventos em tempo real. Exige compilar e manter um build do SoH para Switch. |

Por isso o binding do SoH usa a fonte `save_json` em vez de `memory`. Conteúdo, variáveis, eventos e conquistas são declarados igual aos jogos retail. Ele serve para **qualquer port/homebrew que grave saves legíveis** (a família HarbourMasters, como 2 Ship 2 Harkinian, segue o mesmo `SaveManager`).

## 2. Estrutura do save (verificada no código)

Envelope gravado por `SaveManager::SaveFileThreaded` ([SaveManager.cpp](https://github.com/HarbourMasters/Shipwright/blob/develop/soh/soh/SaveManager.cpp)):

```json
{
  "version": 1,
  "sections": {
    "base":     { "version": 4, "data": { "deaths": 0, "healthCapacity": 48, "inventory": { "equipment": 17, "questItems": 0, "gsTokens": 0 } } },
    "sohStats": { "version": 1, "data": { "itemTimestamps": [], "counts": [], "playTimer": 0, "pauseTimer": 0, "gameComplete": false } }
  }
}
```

No binding, os apelidos `base` e `stats` apontam para `sections.base.data` e `sections.sohStats.data`.

| Campo | Significado | Fonte no código |
|---|---|---|
| `base.inventory.questItems` | Bitfield: bits 0–5 medalhões, 6–17 canções, 18–20 pedras espirituais | `z64item.h` (`QUEST_*`) |
| `base.inventory.equipment` | Bitfield: espadas bits 0–2 (Kokiri, Mestra, Biggoron), escudos 4–6, túnicas 8–10, botas 12–14 | decomp (`gEquipShifts`) |
| `base.inventory.gsTokens` | Gold Skulltula Tokens | `SaveBase` |
| `base.healthCapacity` | Corações × 16 | `SaveBase` |
| `base.deaths` | Mortes no arquivo | `SaveBase` |
| `base.n64ddFlag` / `base.isMasterQuest` | Randomizer / Master Quest | `SaveBase` |
| `stats.itemTimestamps[i]` | Tempo de jogo (décimos de segundo) em que o item *i* foi obtido; `0xA0`–`0xA9` = chefes | `gameplaystats.h` (`TIMESTAMP_*`) |
| `stats.counts[i]` | Contadores (`GameplayStatCount`, 107 entradas no develop) | `gameplaystats.h` (`COUNT_*`) |
| `stats.playTimer` / `pauseTimer` | Tempo: `playTimer/2 + pauseTimer/3` = décimos de segundo | macro `GAMEPLAYSTAT_TOTAL_TIME` |
| `stats.gameComplete` | Jogo zerado | `SaveStats` |

## 3. Conquistas modeladas (34)

O bloco `content` cataloga chefes (com o índice do timestamp e o bit de quest), medalhões, canções, pedras, espadas e contadores de estatística. As conquistas por item são **templates** (`for_each`), não listas escritas à mão.

| Categoria | Conquistas |
|---|---|
| História | template `boss` (8 chefes com bit de quest) e Herói do Tempo (Ganon) |
| Coleção | template `song` (12) e Virtuose da Ocarina, As Três Pedras, Os Seis Sábios, template `sword` (3), 100 Skulltulas, 20 corações |
| Estatísticas | 10 horas de jogo, 1.000 rolamentos, Dark Link |
| Desafios | Gohma em menos de 30 min, zerar sem morrer |

Decisões de robustez:

- **Dupla verificação nos chefes:** o timestamp do chefe (`stats.itemTimestamps[{item.timestamp_index}]`) **ou** o bit de quest. Assim a conquista funciona mesmo em saves antigos, anteriores às estatísticas.
- **Guarda nos contadores:** os índices de `counts` dependem da ordem do enum. As conquistas de estatística exigem `stat_table_size == 107`; em outra versão do SoH elas simplesmente não disparam, em vez de desbloquear errado.
- **`modes`:** o binding classifica cada slot como `default`, `randomizer` ou `master_quest` (`instance_modes`). As conquistas de história ignoram saves de Randomizer, onde itens e recompensas estão embaralhados.
- **Slots combinados:** a conquista desbloqueia se *qualquer* dos três arquivos satisfizer a condição; o progresso mostra o maior valor.
- **Somente leitura:** o save do SoH nunca é modificado.

## 4. Limitações conhecidas

1. **Latência:** o save só muda quando o SoH grava. Com o **Autosave** ligado (Enhancements), a versão develop grava a cada 3 minutos, quando permitido ([`Autosave.cpp`](https://github.com/HarbourMasters/Shipwright/blob/develop/soh/soh/Enhancements/QoL/Autosave.cpp)). Sem Autosave, só ao salvar manualmente. A notificação aparece **depois** do evento, não no instante.
2. **Morte sem salvar:** uma morte só conta se for gravada depois. Isso enfraquece "Zerar sem morrer". Ela é tratada como conquista de honra, e não como prova.
3. **Versão do SoH:** os campos foram conferidos no branch `develop`. Builds de Switch antigos podem ter menos seções. O avaliador mostra a versão do save e marca o que não for suportado.
4. **Menu de cheats do SoH:** ele pode alterar o save, e o sistema não tem como distinguir isso.
5. **Identificação do jogo no console:** como o SoH é homebrew, o Title ID visto pelo sistema é o do jogo "sequestrado" pelo title takeover. O sysmodule vai identificar o SoH pela atividade em `sdmc:/switch/soh/` (mudança de mtime dos saves), e não pelo Title ID.

## 5. Como testar hoje (no PC, com o seu save real)

1. Com o SoH **fechado**, copie `sdmc:/switch/soh/Save/` do cartão SD para o PC.
2. Rode:

   ```bash
   python3 tools/sa.py save games/ship_of_harkinian/definition.json --save-dir /caminho/para/Save --state estado.json --notify-dir notificacoes/
   ```

   A saída mostra o modo de cada slot, cada conquista (`[X]` ou `[ ]`), o progresso, o XP e o nível. Use `--reveal-secrets` para mostrar as secretas.
3. Rodar de novo com o mesmo `--state` mostra só os desbloqueios **novos**: é o comportamento do motor. `--watch` reavalia sempre que um save muda.

### Testar a notificação no Switch (requer Ultrahand ≥ 2.3)

Copie [`examples/ultrahand/SwitchAchievements-teste.notify`](../../examples/ultrahand/SwitchAchievements-teste.notify), ou qualquer arquivo gerado em `notificacoes/`, para `sdmc:/config/ultrahand/notifications/`. O Ultrahand exibe o toast sobre o jogo. É exatamente o caminho que o sysmodule vai usar.

## 6. Próximos passos para este jogo

1. Validar a definição contra o save real do usuário (confirmar versão, `counts.length` e campos presentes).
2. Sysmodule mínimo: a cada 2 s, faz `stat()` em `sdmc:/switch/soh/Save/*.sav`. Quando o mtime muda, lê o arquivo (com nova tentativa se o JSON estiver incompleto), avalia em C++ com a mesma semântica de `tools/sa_core/` e grava o `.notify`.
3. Ícones 50×50 RGBA por conquista.
4. Avaliar a integração nativa via fork do SoH, para ter eventos em tempo real.
