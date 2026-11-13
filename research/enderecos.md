# Endereços de memória: Mario Kart 8 Deluxe e Link's Awakening

Pesquisa de 13/11/2026 em bases públicas de cheats do Atmosphère e em fontes abertas que documentam a memória dos jogos. Nenhum endereço foi inventado. Quando uma variável não aparece em nenhuma fonte, isso está escrito. A forma legível por máquina está em `research/enderecos.json`. Os textos brutos dos cheats estão em `research/cheats/<titleid>/` e as demais fontes em `research/cheats/sources/`.

Legenda de confiança (sugestão, segue `docs/modelo-de-definicao.md` §4):

- **community**: endereço lido diretamente de um cheat ou fonte publicada.
- **assumed**: inferido por nós (ex.: cadeia composta a partir de offsets publicados, bit deduzido, offset igual ao de outro build).
- **to_discover**: não encontrado.

Notação: `[[main+X]+Y]+Z` lê um ponteiro em `main+X`, outro em `+Y` e acessa o campo em `+Z`. No JSON, `chain: ["X","Y"]` e `offset: "Z"`.

## Fontes

| Fonte | Conteúdo útil |
|---|---|
| [HamletDuFromage/switch-cheats-db](https://github.com/HamletDuFromage/switch-cheats-db) (`cheats/`, `cheats_gbatemp/`, `versions/`) | cheats de MK8D/LA e mapa versão → build ID |
| [sthetix/nx-cheats-db](https://github.com/sthetix/nx-cheats-db) | mesma base com mais variantes (MK8D 2.0.0/1.7.1, LA "Girl/Ghost/Gold Leafs/Have All Items") |
| [Arch9SK7/MyNXCheats](https://github.com/Arch9SK7/MyNXCheats/tree/HEAD/Mario%20Kart%208%20Deluxe/0100152000022000/cheats) | cheats de estado do kart do P1 para 2.4.0, 3.0.0, 3.0.1, 3.0.3 e 3.0.5 |
| [xenocard/CheatsHunter](https://github.com/xenocard/CheatsHunter) | cópias e variantes (LA 1.0.1 com hook de acompanhante) |
| [igawa6/eden-duo-companions](https://github.com/igawa6/eden-duo-companions) | mapa de memória do LA 1.0.1 (derivado do código e conferido no jogo) e leitor nativo do MK8D 3.0.3/4.0.0/4.0.1 (offsets do RaceKartChecker, pinos de código com a célula da raiz) |
| [mdietz94/mk8dx_ap](https://github.com/mdietz94/mk8dx_ap/blob/HEAD/docs/symbols.md) | layout dos troféus do Grand Prix no save (4.0.1) e IDs de itens |
| [RoGamer97/ASM-Cheats-and-Patches](https://github.com/RoGamer97/ASM-Cheats-and-Patches/tree/HEAD/Switch/Mario%20Kart%208%20Deluxe) | ASM comentado de 3.0.5/4.0.0/4.0.1 (cadeia da cena até o RaceKartChecker, rank em +0x40) |
| Kenji-NX/switch-pchtxt-mods, zeldamods.org/las/Versions, Nintendo Support | confirmação versão ↔ build ID |

Também foram consultados ibnux/switch-cheat, FlagBrew/Sharkive e blawar/switchcheats. Eles têm só cópias dos mesmos arquivos e não trouxeram nada novo. **Nenhuma base tem cheat de "Always 1st place", "gold trophies in all cups" ou "All instruments"** para estes jogos.

### Lembrete de decodificação usado

- `5T0R00AA AAAAAAAA`: R = u(T) [main+A]. `5T0R10.. AAAAAAAA`: R = [R+A] (próximo nível da cadeia).
- `7T0R0000 VVVVVVVV`: R += V.
- `6T0R0000 00000000 VVVVVVVV`: grava V (largura T) em [R].
- `0TMR00AA AAAAAAAA VVVVVVVV`: grava em região+A. M=0 é main, M=1 é heap e **M=4 (não relativo) usa o registro R como base**: `04420000 000007BC` = [R2+0x7BC].

---

# Mario Kart 8 Deluxe (0100152000022000)

## Versões e build IDs

| Versão | Número | Build ID | Arquitetura | Fonte do mapeamento |
|---|---|---|---|---|
| 1.7.1 | 589824 | FE1B230800D4933C | AArch32 | rótulo do cheat Eiffel2018 + versions.json |
| 1.7.2 | 655360 | 4792ABA465F04534 | AArch32 | idem |
| 2.0.0 | 720896 | 937E57FF64D21ECD | AArch32 | idem |
| 2.1.0 | 786432 | BDA8F5E6A0F87F36 | AArch32 | idem |
| 2.2.0 | 851968 | 60C8343AFBA2588F | AArch32 | versions.json (ordem) |
| 2.2.1 | 917504 | 381F6BF6894F3C33 | AArch32 | versions.json (ordem) |
| 2.3.0 | 983040 | 13296B64DFA7A131 | AArch32 | rótulo "v2.3.0" do cheat |
| 2.4.0 | 1048576 | 4B7A0BB5AE57E627 | AArch32 | versions.json (ordem) |
| 3.0.0 | 1114112 | 94FB3AFECA39D600 | AArch32 | rótulo "v1114112" (Arch9SK7) |
| 3.0.1 | 1179648 | 9EF5CAA2D5B933C7 | AArch32 | rótulo "v1179648" |
| 3.0.3 | 1245184 | 6A85262F21B90364 | AArch32 | eden-duo ("3.0.3 (AArch32)") |
| 3.0.4 | 1310720 | 2452C49BC26EC159 | AArch64 | Kenji-NX `3.0.4.pchtxt` |
| 3.0.5 | 1376256 | **FE941ED5BA14BE5D** | AArch64 | Kenji-NX `3.0.5.pchtxt` |
| 4.0.0 | 1441792 | 2C336A9BCF79C304 | AArch64 | eden-duo / mk8dx_ap |
| 4.0.1 | 1507328 | **158C0C7399AABD7B** | AArch64 | eden-duo / mk8dx_ap (mais recente encontrada, set/2026) |
| 1.0.0 (base) | 0 | B5C39B5B7C62A88E | AArch32 | versions.json |
| ? | ? | 1CD9216A21737FB4, 96DFD1769E560C27 | AArch32 | não constam no versions.json; só têm cheats de heap ("Unlock Gold Mario") |

Observações:

- O binding atual (FE941ED5BA14BE5D, "3.0.x") é o **3.0.5**.
- O jogo virou AArch64 nativo no **3.0.4**. Até o 3.0.3, os ponteiros do processo têm **4 bytes**. Os cheats do Arch9SK7 para esses builds usam `580T` com T=8, lendo 8 bytes por nível; isso só funciona se a palavra seguinte for zero. A leitura correta é u32 por nível. O motor do nx-trophies lê u64 por nível (§6), então os builds AArch32 precisam de largura de ponteiro 4 ou devem ser testados no console antes de virar `community`.
- O versions.json do switch-cheats-db para em 1441792 (4.0.0) e não lista 3.0.4 nem 4.0.1.

## (a) Ponteiro do kart do P1 e campos de estado

O layout relativo é o mesmo em todos os builds com cheat: `star = status+0x18`, `ghost = star+0x8`, `squish = star+0x38`, `shock = star+0x40`, `lakitu = star+0x74`.

| Build | Versão | Ponteiro `p1_kart` | status | star | ghost | squish | shock | lakitu |
|---|---|---|---|---|---|---|---|---|
| 937E57FF64D21ECD | 2.0.0 | `[[main+0xDEE338]+0x1350]` | 0x9D4 | 0x9EC | (0x9F4 assumed) | 0xA24 | 0xA2C | 0xA60 |
| 4B7A0BB5AE57E627 | 2.4.0 | `[[main+0xEFFDD8]+0x1350]` | 0x9D8 | 0x9F0 | (0x9F8 assumed) | 0xA28 | 0xA30 | 0xA64 |
| 94FB3AFECA39D600 | 3.0.0 | `[[main+0xF53448]+0x1350]` | 0x9D8 | 0x9F0 | (0x9F8 assumed) | 0xA28 | 0xA30 | 0xA64 |
| 9EF5CAA2D5B933C7 | 3.0.1 | `[[main+0xF53448]+0x1350]` | 0x9D8 | 0x9F0 | 0x9F8 | 0xA28 | 0xA30 | 0xA64 |
| 6A85262F21B90364 | 3.0.3 | `[[main+0xF53448]+0x1350]` | 0x9D8 | 0x9F0 | 0x9F8 | 0xA28 | 0xA30 | 0xA64 |
| 2452C49BC26EC159 | 3.0.4 | **não encontrado** | | | | | | |
| FE941ED5BA14BE5D | 3.0.5 | `[[main+0x1354AF0]+0x6E0]` | 0x7A4 | 0x7BC | 0x7C4 | 0x7F4 | 0x7FC | 0x830 |
| 2C336A9BCF79C304 | 4.0.0 | **não encontrado** | | | | | | |
| 158C0C7399AABD7B | 4.0.1 | **não encontrado** | | | | | | |

Todos são u32. Confiança: **community** para os offsets gravados por um cheat. Ghost é **assumed** onde não há cheat Ghost. O 2.0.0 tem ainda `P1 Invincible` em +0xA90 (= star+0xA4).

O binding atual do 3.0.5 está **confirmado**. Linhas exatas ([Arch9SK7 FE941ED5BA14BE5D.txt](https://github.com/Arch9SK7/MyNXCheats/blob/HEAD/Mario%20Kart%208%20Deluxe/0100152000022000/cheats/FE941ED5BA14BE5D.txt), cópia em `research/cheats/0100152000022000/FE941ED5BA14BE5D.Arch9SK7.txt`):

```
{Mastercode}
...
58020000 01354AF0        ; R2 = [main+0x1354AF0]
58021000 000006E0        ; R2 = [R2+0x6E0]          -> p1_kart

[Press D-UP P1 Star Power]
80002000
04420000 000007BC 000001BF   ; u32 [R2+0x7BC] = 0x1BF
20000000
[Press D-RIGHT P1 Controlled Bullet Bill]
04420000 000007A4 00A01000
[Press D-LEFT P1 Normal Status]
04420000 000007A4 00801000
[Press D-DOWN P1 Lakitu Pickup]
04420000 00000830 000001BF
[Press L-STICK P1 Shocked]
04420000 000007FC 00000175
[Press R-STICK P1 Squished]
04420000 000007F4 00000120
[Press R-STICK P1 Ghost Mode]
04420000 000007C4 00000120
[Press L-STICK P1 Wing Deployement]
04420000 000007A3 00000175   ; u32 em endereço ímpar, sobrepõe os bytes de status (anomalia do cheat)
```

Formato dos builds AArch32 (exemplo do 3.0.1, [switch-cheats-db](https://github.com/HamletDuFromage/switch-cheats-db/blob/master/cheats/0100152000022000.json)):

```
[Press D-UP P1 Star Power]
80002000
58020000 00F53448        ; R2 = [main+0xF53448]
58021000 00001350        ; R2 = [R2+0x1350]
78020000 000009F0        ; R2 += 0x9F0
64020000 00000000 000001BF
20000000
```

No 2.0.0 ([sthetix](https://github.com/sthetix/nx-cheats-db/blob/HEAD/cheats/0100152000022000.json)), a cadeia é `58020000 00DEE338 / 58021000 00001350`, com `78020000 000009EC` (star), `000009D4` (Bullet Bill/status), `00000A60` (lakitu), `00000A2C` (shock), `00000A24` (squish) e `00000A90` ("P1 Invincible"). No 2.4.0 (Arch9SK7), a cadeia é `58020000 00EFFDD8 / 58021000 00001350` com os mesmos offsets do 3.0.x.

## (b) Moedas do P1

| Build | Endereço | Tipo | Confiança | Base |
|---|---|---|---|---|
| 1.7.1 FE1B230800D4933C | `[main+0xDA9EA8]+0xC28FC` | u32 | community | cheat "Grand Prix - Always 10 Coins" |
| 2.0.0 937E57FF64D21ECD | `heap+0x5860CACC` | u32 | assumed (heap estático, instável) | cheat "99 Coins" `04100000 5860CACC 00000063` |
| 3.0.3 6A85262F21B90364 | `p1_checker+0x34` | u8 | assumed | eden-duo (perfil 3.0.3) |
| 3.0.5 FE941ED5BA14BE5D | `RaceKartChecker+0x50` (raiz não pública) | u32/u8 | to_discover | hook do Arch9SK7 |
| 4.0.0 / 4.0.1 | `p1_checker+0x50` | u8 | assumed | eden-duo |
| demais | não encontrado (só patches de código do Eiffel2018) | | to_discover | |

Linhas do 1.7.1 ([sthetix](https://github.com/sthetix/nx-cheats-db/blob/HEAD/cheats/0100152000022000.json)):

```
[Grand Prix - Always 10 Coins]
58000000 00DA9EA8            ; R0 = [main+0xDA9EA8]
98010100 00000000 000C28FC   ; R1 = R0 + 0xC28FC
54011000 00000000            ; R1 = u32 [R1]          (moedas)
C0431400 0000000A            ; se R1 < 10:
40010000 00000000 0000000A   ;   R1 = 10
A4100200 000C28FC            ;   u32 [R0+0xC28FC] = R1
20000000
```

Linhas do 3.0.5 ([Arch9SK7](https://github.com/Arch9SK7/MyNXCheats/blob/HEAD/Mario%20Kart%208%20Deluxe/0100152000022000/cheats/FE941ED5BA14BE5D.txt)):

```
[№ 3. Always Max Coins]
040A0000 0087C994 140B51D1   ; desvia a instrução original para a code cave
040A0000 00B510D8 18000074   ; ldr w20, =10   (literal em 0xB510E4 = 0x0000000A)
040A0000 00B510DC B9005274   ; str w20, [x19, #0x50]   <- instrução original do jogo
040A0000 00B510E0 17F4AE2E   ; volta
```

A instrução original `B9005274` decodifica para `str w20,[x19,#0x50]`, ou seja, as moedas ficam em +0x50 do objeto em x19. Isso coincide com `ck_coins = 0x50` do RaceKartChecker no eden-duo (4.0.0/4.0.1) e com a nota do mk8dx_ap de que o RaceKartChecker não mudou entre 3.0.5 e 4.0.0. Não há caminho estático publicado até esse objeto no 3.0.5 (ver (c)).

Os cheats "5x Coins Collected / No Coins Dropped" do Eiffel2018 (todos os builds AArch32) são hooks em ARM32. Eles só mostram que o jogo testa `ldrb r2,[r4,#0x1C]` (índice do jogador == 0) antes de somar moedas. Não dão endereço de dado.

## (c) Colocação e corrida terminada

Nenhum cheat "Always 1st place" foi encontrado. Os dados vêm do **RaceKartChecker** (um por corredor), documentado em duas fontes abertas:

- eden-duo `mk8d_reader.h/.cpp`: rank = `u16 CK+0x40` (0-based), volta = `u32 CK+0x44`, moedas = `u8 CK+0x50`, chegada = **bit 0 de `u32 CK+0x3C`**. No 3.0.3 os offsets são 0x24 / 0x28 / 0x34 / 0x20. A fase da corrida é `u32 [[RD+0x50]+0x38]`, com 6 = correndo e 7 = jogador local terminou.
- RoGamer97, "Replace FINISH! with YOU WIN!" (3.0.5/4.0.0/4.0.1), [source.s](https://github.com/RoGamer97/ASM-Cheats-and-Patches/blob/HEAD/Switch/Mario%20Kart%208%20Deluxe/3.0.5/Replace%20FINISH!%20with%20YOU%20WIN!%20or%20YOU%20LOSE%20Based%20on%20Result/source.s):

```
BL 0x7F41FC        //; gear::FrameworkUtil::getCurrentGameScene(void)   (3.0.5; 4.0.0 = 0x7F7AC0)
LDR X8, [X0, #0x1B0]
LDR X8, [X8, #0x218]
LDR X8, [X8, #0x68]
LDR X8, [X8,X1,LSL#3] //; gear::RaceKartChecker*
LDR W0, [X8, #0x40]   // rank
//; getMyKartIndex returns -1 offline ... your ID is always 0 offline.
```

A célula estática da raiz foi decodificada dos pinos de código do eden-duo (`mk8d_pins.inc`, `mk8d_pins401.inc`, `mk8d_pins303.inc`):

| Build | Instruções | Célula (GOT) | root |
|---|---|---|---|
| 4.0.0 | `0x7f7a90 adrp x8,#0x12fc000` / `ldr x8,[x8,#0x388]` / `ldr x8,[x8]` | main+0x12FC388 | `[[main+0x12FC388]]` |
| 4.0.1 | `0x7e7404 adrp x8,#0x12fb000` / `ldr x8,[x8,#0x388]` | main+0x12FB388 | `[[main+0x12FB388]]` |
| 3.0.3 | `ldr r0,[pc,#0x10]` (lit 0x698b18) / `ldr r0,[pc,r0]` → 0xF12C68 | main+0xF12C68 (ponteiros u32) | `[[main+0xF12C68]]` |
| 3.0.5 | não publicado (precisa desmontar `getCurrentGameScene` em main+0x7F41FC) | — | — |

Cadeia composta (**assumed**: cada passo vem de uma fonte publicada, mas a cadeia inteira não aparece em nenhum cheat):

```
4.0.0  p1_checker = [[[[[[[[main+0x12FC388]+0x0]+0x20]+0x8]+0x1B0]+0x218]+0x68]+0x0]
4.0.1  p1_checker = mesma cadeia com 0x12FB388
3.0.3  p1_checker = [[[[[[[[main+0xF12C68]+0x0]+0x10]+0x4]+0xF0]+0x11C]+0x3C]+0x0]   (u32 por nível)
         root -> +0x20 cena(holder) -> +0x8 cena -> +0x1B0 ObjectEngine -> +0x218 RaceDirector
         -> +0x68 vetor de checkers -> [0] = corredor 0 (= jogador local offline)
race.final_rank = u16 p1_checker+0x40 (+1 para exibir)     race.finished = u32 p1_checker+0x3C & 1
```

Antes de ler, valide a cena: `u32 scene+0x184 == 4` (Race) e `u8 scene+0x180 & 4` (ativa). No 3.0.3 os offsets equivalentes são 0xD8 e 0xD4. Fora da corrida, a cadeia aponta para outra cena. Sugestão: `active_when` nessa condição.

## (d) Troféus do Grand Prix (150cc)

Não existe cheat público de "gold trophies all cups" para nenhum build. O layout vem da análise estática do 4.0.1 no mk8dx_ap ([docs/symbols.md](https://github.com/mdietz94/mk8dx_ap/blob/HEAD/docs/symbols.md), seção "Grand Prix result"):

> It stores max(old, new) at `save+0x188 -> +0x688 + engine * 0x20 + cup` (stars at `+0x588`); `Control_TrophyIcon::setCup` (`+0x479D98`) reads the same bytes. ... entry[2] = final placing (1/2/3 -> trophy byte 3/2/1)

- Tabela: `prog = [save+0x188]`. O troféu fica em `u8 prog + 0x688 + engine*0x20 + cup`.
- `engine`: 0 = 50cc, 1 = 100cc, **2 = 150cc**, 3 = 200cc, 4 = espelho. Em 150cc o endereço é `prog+0x6C8+cup`.
- Stride por copa: **1 byte**. Stride por cilindrada: 0x20 (até 32 copas).
- Valores: **0 nenhum, 1 bronze, 2 prata, 3 ouro** (o jogo guarda o máximo). Estrelas (0..3) ficam em `prog+0x588+engine*0x20+cup`. Flags de copa aberta ficam em `prog+0x1F20+cup` (3 = aberta).
- Índice da copa: `ECup`, 0-based, com 0 = Cogumelo (confirmado no `CupGateHook.cpp`). A ordem das demais copas **não está publicada**: os headers deixam o enum vazio. O `trophy_index` de cada copa continua **to_discover**.
- Caminho até `save`: `gear::GetCurrentUserSaveData` termina em `ldr x8,[x0,#0x810]` / `ldr x0,[x8,#0x158]`, e `GetPlayerManager` termina em `ldr x0,[x0,#0x800]`. O eden-duo mostra que `PlayerManager = [SystemEngine+0x800]`, com `SystemEngine = [[root+0x28]+0x190]`. Daí, por inferência, `save = [[SystemEngine+0x810]+0x158]`:

```
4.0.1  save_progress = [[[[[[[main+0x12FB388]+0x0]+0x28]+0x190]+0x810]+0x158]+0x188]
       cup.best_trophy_150cc[cup] = u8 save_progress + 0x6C8 + cup
4.0.0  mesma cadeia com 0x12FC388 (layout do save analisado no 4.0.1; assumed)
```

Confiança: **assumed**. O prefixo até `save` é inferido, e a ordem das copas não é conhecida. Nos builds AArch32 antigos, os cheats "Unlock Gold Mario" (`01100000 29AF136D 00000003`) e "Unlock All Parts" (bytes 03 em `heap+0x29AF1388..`) mostram a mesma convenção "3 = desbloqueado" na tabela de flags, mas com endereços estáticos no heap. Não servem para ler troféus.

## (e) Bullet Bill e itens

- **Estado "virou Bullet Bill"**: o campo `status` do kart recebe `0x00A01000` no cheat "Controlled Bullet Bill" e `0x00801000` em "Normal Status", nos builds 2.0.0, 2.4.0, 3.0.0, 3.0.1, 3.0.3 e 3.0.5. Que o bit `0x00200000` signifique Bullet Bill é **assumed**.
- **ID do item**: `Killer` (Bullet Bill) = **9** em `gear::EItemSlot` ([mk8dx_ap Ids.hpp](https://github.com/mdietz94/mk8dx_ap/blob/HEAD/switch-mod/src/game/Ids.hpp)). Isso bate com o cheat 3.0.5 "P2 Set Next Item Bullet Bill" (`08000000 013628E0 00000000 00000009`). As escritas em `main+0x13628D0/E0` desses cheats alimentam o hook do Master Code; não são estado do jogo.
- **Item na mão (4.0.x)**, pelo eden-duo: `ItemDirector = [ObjectEngine+0x240]`, owners em `[ItemDirector+0xE8]` (contagem u32 em +0xE0), com `owner[i]+0x40 == i`. Os slots ficam em `[owner+0x60]` e `[owner+0x68]`. Em cada slot: `u8 +0x41` é o estado (0 vazio, 1-2 roleta, 3 segurando), `u32 +0xC8` o item e `u32 +0xA0` a quantidade. Confiança: assumed.
- Estado do kart (estrela, fantasma etc.) para 3.0.4, 4.0.0 e 4.0.1: **não encontrado**.

## Resumo por build (MK8D)

| Build | Versão | kart P1 | moedas | rank/chegada | troféus |
|---|---|---|---|---|---|
| FE1B230800D4933C | 1.7.1 | não | community `[main+0xDA9EA8]+0xC28FC` | não | não |
| 937E57FF64D21ECD | 2.0.0 | community | heap (instável) | não | não |
| 4B7A0BB5AE57E627 | 2.4.0 | community | não | não | não |
| 94FB3AFECA39D600 | 3.0.0 | community | não | não | não |
| 9EF5CAA2D5B933C7 | 3.0.1 | community | não | não | não |
| 6A85262F21B90364 | 3.0.3 | community (cadeia u32) | assumed | assumed | não |
| 2452C49BC26EC159 | 3.0.4 | não | não | não | não |
| FE941ED5BA14BE5D | 3.0.5 | community (= binding atual) | offset +0x50, raiz não pública | offset +0x40, raiz não pública | não |
| 2C336A9BCF79C304 | 4.0.0 | não | assumed | assumed | assumed |
| 158C0C7399AABD7B | 4.0.1 | não | assumed | assumed | assumed |

Os builds 1.7.2, 2.1.0, 2.2.0, 2.2.1 e 2.3.0 só têm patches de código do Eiffel2018 (desbloqueios, limite de moedas, tamanho), sem endereços de dado.

---

# The Legend of Zelda: Link's Awakening (01006BB00C6F0000)

## Versões e build IDs

| Versão | Número | Build ID | Observação |
|---|---|---|---|
| 1.0.0 | 0 | AE16F71E002AF8CB | lançamento |
| 1.0.1 | 65536 | 909E904AF78AC1B8 | correção da Marin; "none of the offsets in the code have been changed" (ZeldaSpeedRuns) |
| 1.1.0 | 131072 | 909E904AF78AC1B8 | mesmo build ID; só `main.npdm` mudou (zeldamods.org) |

Os endereços são **iguais** nos dois builds. Os cheats publicados para os dois usam os mesmos offsets (rúpias, corações, pó, bombas, flechas, chaves, ponteiro do High Jump `[[[main+0x1CC8B50]+0x1528]+0x928]+0x18`). O mapa do eden-duo diz ".bss layout identical to 1.0.0".

## Variáveis

| Variável | Endereço | Tipo | Significado | Confiança | Fonte |
|---|---|---|---|---|---|
| rupees | main+0x1CC0760 | u16 | rúpias | community | ambos os builds |
| trade_item | main+0x1CC077A | u8 | 1..14 (abaixo) | community | AE16 (cheats), 909E (eden-duo) |
| follower | main+0x1CC077D | u8 | 1 Marin?, 3 Fantasma, 4 Galinha | community no AE16 (Marin assumed); assumed no 909E | sthetix/xenocard |
| golden_leaves | main+0x1CC07A2 | u8 | bits 0..4 (0x1F) | community | sthetix AE16 + eden-duo 909E |
| figures | main+0x1CC07C8 | u16 | máscaras (abaixo) | community | cheats AE16 + eden-duo |
| **instruments** | **main+0x1CC078C** | **u32** | **bits 7..14** | assumed (ordem dos bits) | eden-duo 909E |
| dungeon.small_keys | main+0x1CBB300 + **0x20**·n | u8 | chaves pequenas | community | cheats + eden-duo |
| dungeon.treasures | main+0x1CBB301 + **0x20**·n | u8 | b0 bússola, b1 mapa, b2 bico, b3 chave do pesadelo | community | cheats (0x0F) + eden-duo (bits) |
| dungeon.current (extra) | main+0x1CC13C8 | u8 | 0-7 Nv1-8, 8 Câmara, 9 Cores, 255 fora | community (909E) | eden-duo |

### (a) Instrumentos

Não existe cheat "All instruments". O mapa do eden-duo para o 1.0.1 ([909E904AF78AC1B8.json](https://github.com/igawa6/eden-duo-companions/blob/HEAD/packages/LinksAwakening/dualscreen/909E904AF78AC1B8.json), "derived from the game's code and checked against the running game") define:

```
key_items        u32 main+0x1CC078C   observed: 0x1FFFF
inst_0..inst_7   u32 main+0x1CC078C bit 7..14  "instrument i = key_items bit 7+i (Cello..Drum)"
instrument_count popcount dos bits 7..14 (guest InstrumentCount = 8)
outros bits: 0 nadadeiras, 1 remédio, 2 Tail Key, 3 Slime Key, 4 Angler Key, 5 Face Key, 6 Bird Key, 15 cogumelo, 16 sensor
```

Layout sugerido: máscara total **0x7F80**.

| Instrumento | Bit | Máscara (u32 em 0x1CC078C) | Alternativa em bytes |
|---|---|---|---|
| Full Moon Cello | 7 | 0x0080 | u8 0x1CC078C & 0x80 |
| Conch Horn | 8 | 0x0100 | u8 0x1CC078D & 0x01 |
| Sea Lily's Bell | 9 | 0x0200 | 0x1CC078D & 0x02 |
| Surf Harp | 10 | 0x0400 | 0x1CC078D & 0x04 |
| Wind Marimba | 11 | 0x0800 | 0x1CC078D & 0x08 |
| Coral Triangle | 12 | 0x1000 | 0x1CC078D & 0x10 |
| Evening Calm Organ | 13 | 0x2000 | 0x1CC078D & 0x20 |
| Thunder Drum | 14 | 0x4000 | 0x1CC078D & 0x40 |

O endereço e a máscara 0x7F80 são consistentes com o cheat "Have All Items" (1.0.0), que grava `04000000 01CC078C 000FFFFF` e com isso liga todos os bits 0..19. A ordem por instrumento segue o rótulo "Cello..Drum" da fonte, mas só o total (popcount = 8) foi observado explicitamente. Sugestão: **assumed** por instrumento até conferir no console. O binding atual (`instruments` u8 com bits 0..7) **não serve**: é preciso ler u16/u32 em 0x1CC078C com máscara `0x80 << i`.

### (b) Masmorras: correção importante

O **stride é 0x20**, não 0x10. Registro n = `main+0x1CBB300 + 0x20*n`:

- `+0` = chaves pequenas (u8)
- `+1` = tesouros: **b0 bússola, b1 mapa, b2 bico de pedra, b3 chave do pesadelo**
- `+8` = salas visitadas (u64, bit = linha*8+coluna)
- Índice: **0..7 = Nível 1..8** (Tail Cave .. Turtle Rock), **8 = Câmaras do Dampé**, **9 = Masmorra das Cores**.

Com isso, o `slot` em `games/zelda_links_awakening.json` deveria usar stride 0x20, e a Masmorra das Cores é o slot **9**, não 8.

Linhas do cheat (1.0.0, [switch-cheats-db](https://github.com/HamletDuFromage/switch-cheats-db/blob/master/cheats/01006BB00C6F0000.json)):

```
[Have Map/Compass/Nightmare Key/Stone Beak]
01000000 01cbb301 0000000f
01000000 01cbb311 0000000f
01000000 01cbb321 0000000f
01000000 01cbb331 0000000f
01000000 01cbb341 0000000f
01000000 01cbb351 0000000f
01000000 01cbb361 0000000f
01000000 01cbb371 0000000f
01000000 01cbb381 0000000f
01000000 01cbb3a1 0000000f
01000000 01cbb3c1 0000000f
01000000 01cbb3e1 0000000f
01000000 01cbb421 0000000f
[Infinite Small Keys]
01000000 01cbb300 00000001   ... mesmos endereços com +0 (…310, 320, …, 380, 3a0, 3c0, 3e0, 420)
```

O cheat grava a cada 0x10 até 0x380 e depois a cada 0x20 (0x3A0, 0x3C0, 0x3E0, 0x420). Os múltiplos de 0x20 batem com os registros 0..7 e 9. As escritas em 0x310, 0x330 etc. caem em `+0x10` de outro registro e são excesso do cheat. A variante do sthetix ("Have Map/Compass/Boss Key & Other Items In Map Screen") grava só `01CBB301` e `01CBB321`, o que também indica stride 0x20. O eden-duo lista `dgn_*_0..7` em 0x1CBB301, 0x321, 0x341, 0x361, 0x381, 0x3A1, 0x3C1, 0x3E1 e `dgn_*_9` em 0x1CBB421.

### (c) Itens de troca

Confirmados por cheat no 1.0.0 (um cheat por item em `01000000 01cc077a 000000VV`), e no 1.0.1 pelo eden-duo ("0 none, 1 Yoshi Doll .. 14 Magnifying Lens"):

```
[  Yoshi Doll]   01000000 01cc077a 00000001
[  Ribbon]       01000000 01cc077a 00000002
[  Dog Food]     ... 03   [  Bananas] 04   [  Stick] 05   [  Honeycomb] 06
[  Pineapple]    01000000 01cc077a 00000007
[  Hibiscus] 08  [  Goat's Letter] 09  [  Broom] 0a  [  Fishing Hook] 0b
[  Necklace] 0c  [  Mermaid's Scale] 0d  [  Magnifying Lense] 0e
```

Yoshi Doll = 1, Ribbon = 2 e Pineapple = 7 podem passar de `assumed` para **community**.

### Outras observações

- **Figurinhas**: os cheats dão `CiaoCiao 0x1, Goomba 0x2, Spiny 0x4, Boo 0x8, Cheep Cheep 0x10, Blooper 0x20, Shy Guy 0x40, Piranha Plant 0x80, Pokey 0x100 (u16), BowWow 0x200 (u16)`. O `games/zelda_links_awakening.json` atual tem **shy_guy = 0x0004**, mas 0x4 é o Spiny e o Shy Guy é **0x0040**.
- **Acompanhante**: os cheats do 1.0.0 dão `Girl` = 1, `Ghost` = 3 e `Blue Chicken` = 4 (`01000000 01CC077D 0000000V`). Há conflito no valor da Marin: o xenocard 1.0.0 lista "Dog on Chain" = 1 e "Girl" = 1, e um hook do 1.0.1 (`04000000 01431168 0000000V`, que é parâmetro do hook e não o byte de estado) usa 1 = BowWow, 2 = Marin, 3 = fantasma, 4 = galinha. Fantasma = 3 é seguro. Marin = 1 deveria ficar **assumed**.
- Extras do mesmo bloco (eden-duo/cheats): canções `u8 0x1CC077B` (b0 Ballad, b1 Mambo, b2 Frog), melhorias `u8 0x1CC077C`, conchas secretas `u64 0x1CC076C`, slots de itens `u32 0x1CC0788`, corações `0x1CC0764` (quartos de coração), mortes `0x1CC05A4`.

---

## O que continua desconhecido

- **MK8D 3.0.4 (2452C49BC26EC159)**: nenhum endereço de dado publicado.
- **MK8D 3.0.5**: moedas, rank e chegada têm offsets conhecidos no RaceKartChecker (+0x50, +0x40, +0x3C), mas falta a célula GOT da raiz (desmontar `getCurrentGameScene` em main+0x7F41FC). Troféus: nada.
- **MK8D 4.0.0/4.0.1**: estado do kart (estrela, fantasma, choque, Lakitu, status Bullet Bill) não encontrado. A ordem `ECup` → copa (o `trophy_index`) não está publicada. Todas as cadeias propostas são `assumed` até testar no console.
- **MK8D builds AArch32**: o motor lê u64 por nível; precisa suportar ponteiro de 4 bytes ou ser validado no console.
- **LA**: ordem individual dos bits de instrumento (só o total foi observado), valor da Marin no acompanhante e significado de "Câmara" (índice 8) não confirmados no console.

## Arquivos baixados

- `research/cheats/0100152000022000/<BUILD>.txt`: cheats do switch-cheats-db (cheats + cheats_gbatemp, mesclados).
- `research/cheats/0100152000022000/<BUILD>.sthetix*.txt`: variantes do sthetix/nx-cheats-db.
- `research/cheats/0100152000022000/<BUILD>.Arch9SK7.txt`: arquivos do Arch9SK7.
- `research/cheats/01006BB00C6F0000/<BUILD>.txt`, `.sthetix*.txt`, `.xenocard.txt`.
- `research/cheats/raw/`: JSON originais do switch-cheats-db, incluindo `versions_*.json`.
- `research/cheats/sources/`: eden-duo (mapa LA, leitor e pinos MK8D), mk8dx_ap (symbols.md, Ids.hpp, Structs.hpp), RoGamer97 (`rogamer97/*.s`), xenocard, lingxup, homenx.
