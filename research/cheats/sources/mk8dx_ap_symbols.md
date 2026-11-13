# Symbols: how the mod finds game functions, and where the data comes from

The mod supports exactly one game build: **MK8DX 4.0.1**, main build id
`158C0C7399AABD7BF83795C2EF3484C7`. On any other build (4.0.0 included:
`2C336A9BCF79C3040CE506CDD391B578`) `hkMain` logs an error and installs
nothing. The mod targeted 4.0.0 until 2026-10-21; 4.0.0 support was
dropped rather than kept alongside (user decision: latest version only).

MK8DX ships no symbols. `switch-mod/syms/mk8dx_symbols.toml` lists every
game function the mod hooks or calls. `src/sym/PatternResolver.cpp` locates
each one at boot:

| Locator | Used for | How |
|---|---|---|
| `address` | functions with a published 4.0.1 address | used as-is |
| `pattern` + `offset`, exact | everything else | byte pattern scanned over main `.text` at instruction alignment; must match once |
| `pattern`, relaxed | when the exact bytes miss | branch distances, ADRP pages and struct-offset immediates wildcarded; must match exactly once |

The patterns were authored against 3.0.5, which is why the relaxed pass
exists: between 3.0.5 and 4.0.0 most code is byte-identical, but relative
branches always differ and some struct members moved. When an entry has
both an address and a pattern, the pattern result is logged next to the
address; that tells you how well the 3.0.5-era patterns carry over and so
how much to trust the pattern-only entries.

The boot log prints one line per entry (`published address`, `pattern`,
`RELAXED pattern` or `UNRESOLVED`) and `resolved N/M`. A hook whose symbol
is unresolved skips itself. The `hello` message carries the counts and the
unresolved names, and the PC client says which features are off.

SDK functions (`nn::socket`, `nn::nifm`, `nn::os`, `nn::prepo`) are not in
this table: they are exported by the game / sdk modules and resolved by
name through nnrtld (`HkTrampoline::installAtSym`,
`--unresolved-symbols=ignore-all`).

## Current table (4.0.1)

Boot on a real 4.0.1 dump (XCI base + v1507328 update, Ryujinx 1.3.3,
2026-10-21): build id `158C0C7399AABD7BF83795C2EF3484C7` matched, 20/21
resolved, every hook installed, client handshake OK. Every pattern hit
moved by the same per-region delta as Ro's published addresses (last
column), which is how the pattern hits were checked to be the right
functions.

| Function | Locator (4.0.1) | 4.0.0 | Delta |
|---|---|---|---|
| `gear::GetRaceInfo` | address `0x86F7BC` | `0x87FCD0` | -0x10514 |
| `gear::FrameworkUtil::getCurrentGameScene` | address `0x7E7434` | `0x7F7AC0` | -0x1068C |
| `gear::NetworkUtil::getMyKartIndex` | address `0x852234` | `0x862820` | -0x105EC |
| `ui::RaceWindow::onFakeGoal` | address `0x5502F0` (Ro hooks `+0xD8` at `0x5503C8`) | `0x550168` | +0x188 |
| `gear::ItemOwner::startSlot` | address `0x43374` | `0x4336C` | +0x8 |
| `ui::SetRandomCPU` | address `0x4FD858` (Ro hooks `+0x2140` at `0x4FF998`) | `0x4FD6D0` | +0x188 |
| `gear::GetNextRaceInfo` | pattern, exact hit `+0x86F7D4` | `+0x87FCE8` | -0x10514 |
| `gear::FlagAccessor::isOpen` | pattern, exact hit `+0x865E7C`; fires per cup on the title-screen cup grid | `+0x876370` | -0x104F4 |
| `gear::DLCManager::getCupStatus` | pattern **UNRESOLVED** (no exact hit, relaxed form not unique; same on 4.0.0). Layer 2 of the cup gate is skipped; layers 1 and 3 cover it | - | - |
| `ui::SetNextCourse` | pattern, RELAXED hit `+0x41FE64` (the 3.0.5 `#0x1744 -> #0x1A44` member move) | `+0x41FCF8` | +0x16C |
| `ui::Control_CupButton::setCup` | pattern, exact hit `+0x43BB68` | `+0x43B9FC` | +0x16C |
| `ui::Control_RaceLapCoin::onCalc_` | pattern, exact hit `+0x512E0C` | `+0x512C84` | +0x188 |
| `gear::SaveDataFile::load` | pattern, exact hit `+0x8DADC4`; fires twice at boot | `+0x8EB2D8` | -0x10514 |
| `gear::GetCurrentUserSaveData` | pattern, exact hit `+0x8AD024` | `+0x8BD538` | -0x10514 |
| `gear::GetPlayerManager` | pattern, exact hit `+0x8ACE28` | `+0x8BD33C` | -0x10514 |
| `ui::Page_CourseBase::isDLC` | pattern, exact hit `+0x494E44` | `+0x494CD8` | +0x16C |
| `object::KartDirector::prepareBeforeStructure` | pattern, exact hit `+0x13D778` | `+0x13D588` | +0x1F0 |
| `mush::E{Driver,Body,Tire,Wing}ID::text_` | pattern, exact hits `+0xB51E0 / +0xB5574 / +0x16BA5C / +0x13336C`; tables enumerate 54 / 42 / 23 / 16 entries (as on 4.0.0) | `+0xB4FF0 / +0xB5384 / +0x16B86C / +0x13317C` | +0x1F0 |
| `object::KartVehicle::setupStatParam` (our name; unnamed in public sources) | address `0x170738`, pattern exact hit at the same place (4.0.1 disassembly, 2026-11-09) | - | - |
| `ui::GrandPrix::commitResult` (our name; unnamed in public sources) | address `0x552FB0`; pattern starts 0x18 in (the prologue is shared by 98 functions), unique (4.0.1 disassembly, 2026-11-10) | - | - |
| `gear::FlagAccessor::isOpen(EDriverID / EBodyID / ETireID / EWingID)` | pattern, exact hits `+0x865F14 / +0x865F60 / +0x865FAC / +0x865FF8` (located in the 4.0.1 disassembly, 2026-11-04; booted and installed in Ryujinx the same day) | - | - |

## What changed in 4.0.1 (from Ro's port)

Checked against every 4.0.0 / 4.0.1 `source.s` pair on 2026-10-21 (30
pairs): with addresses masked, the sources are identical except one GOT
slot (`ADRP #0x1306000; LDR X0, [X0, #0xE78 -> #0xE70]`, a `sead::Random`
pointer the mod does not use). No struct offset or pointer chain the mod
uses changed. Code moved by region: about `+0x8` low in `.text`, `+0x16C`
to `+0x1F0` in the UI / object code, `-0x105xx` from roughly `0x7E0000`
up. Relative layout inside the hooked functions is unchanged (Ro's
`onFakeGoal + 0xD8` and `SetRandomCPU + 0x2140` hook offsets are the same).

## Findings from the 4.0.0 sessions (still apply: 4.0.1 code is the same)

First boot on a real 4.0.0 dump (Ryujinx 1.3.3, 2026-10-16): build id
`2C336A9BCF79C3040CE506CDD391B578` matched, 16/17 resolved.

### Calling-convention findings from that boot

* `mush::E*ID`, `ui::ECup` and `ui::DLCState` are class wrappers and are
  passed **by const reference**: the hooked functions receive a pointer to
  a 32-bit value on the caller's stack in x1/x2. Declaring those arguments
  as `int` truncated the pointers inside `orig()` and crashed the Prepare
  Thread at boot. Every pattern-located hook now forwards x1..x5 as `u64`
  and dereferences only when the register looks like a pointer.
* `ui::ECup` is **0-based** (Mushroom = 0 ... Spiny = 23) and equal to
  `mush::EGrandPrixID`: the cup grid calls `isOpen(gp=N)` then
  `setCup(ecup=N)` for each cup. BCP cups the save does not own arrive as
  `DLCState` 2 (NotBuy).
* The nn::prepo IPC proxy symbols on MK8DX's NintendoSDK 4.4.0 are
  `CmifProxyImpl<IPrepoService, CmifDomainProxy<...MessageType 4...>,
  MemoryResourceAllocationPolicy, IPrepoService>` with no
  `ProcessModifierImpl` suffix (SDK 15+ names differ). `SdkSymbolDump.cpp`
  logs the exact mangled names at boot; both SaveReport hooks install.
* First race (GP 50cc, Mushroom Cup race 1, 2026-10-16): `ui::SetNextCourse`
  fired with course id 27 (and 28 for the next race preview), the speed hook
  read `top=8.325/6.460/6.460` (offsets sane), `onFakeGoal` fired once per
  RaceWindow (5 windows, every auto-finished kart, not just the player; the
  hook now keeps only the kart whose KartVehicle is master), `RaceWindow+0xF4`
  does not hold the kart index on 4.0.0 (reads -1; the window-id derivation
  is used), ranks are 0-based, and the `match` PlayReport decoded to
  `Course=Gu_FirstCircuit Rank=1 Rule=GP Engine=50cc`. Course id 27 was
  learned as Mario Kart Stadium from the hook + report pairing.
* Added after the first live-seed session (2026-10-16), all pattern hits on 4.0.0:
  `ui::SetRandomCPU` (published `0x4FD6D0`), `object::KartDirector::prepareBeforeStructure`
  (`+0x13D588`), `gear::GetPlayerManager` (`+0x8BD33C`), `ui::Page_CourseBase::isDLC`
  (`+0x494CD8`). 20/21 resolve; only `DLCManager::getCupStatus` is still unresolved.
* **Loadout enforcement**: rewriting `GetNextRaceInfo()`/`GetRaceInfo()` kart infos at
  `SetNextCourse`, after `SetRandomCPU`, or even pre-orig in
  `KartDirector::prepareBeforeStructure` never changed the race (PlayReport kept the
  menu pick). The human selection lives in `gear::Player::mKartInfo` (`Player+0x210`,
  `PlayerManager+0x50` PtrArray, 16 slots, `+0x178` local count); rewriting it there
  works. RaceInfo is downstream of it.
* **Cup gate**: `FlagAccessor::isOpen` returning false soft-locks cup select (Deluxe has
  no closed-cup UI path). `Control_CupButton::setCup`'s DLCState is display only, and
  `Control_CupButton+0x3CB` is 1 for every cup (not a lock flag). The working gate is
  `static DLCState Page_CourseBase::isDLC(ECup)`: DLCState has a user-declared
  destructor, so it is returned through the hidden x8 pointer and ECup is passed by
  reference; the hook entry is an asm stub (`mk8ap_isDlcEntry`) that forwards x8.
  Returning `Locked(4)` (the pre-release Booster Course Pass state) draws a padlock and
  makes the cup unselectable. **Superseded in 0.2.1**: Locked disables the button
  (`Control+0x3CB` = 0), and the cursor cannot cross disabled buttons, so an open cup
  boxed in by locked ones could not be reached (player report 2026-10-25). See below.
* **Cup gate, 4.0.1 disassembly (2026-10-25)**: `isDLC` (`+0x494E44`) returns `Locked`
  for a base cup whose `FlagAccessor::isOpen` is false, `Unlocked` for an open one, and
  for BCP cups `Unlocked` / `NotSale` / `NotBuy` from `DLCManager`. Callers:
  grid setup (`+0x494B..`, `+0x4955..`) sets `+0x3CB = (state != Locked)`, the generic
  Control "enabled" byte (input gating, greyed animation); focus preview (`+0x494F08`)
  shows "???" course names for states 0, 1, 4; cup decide (`+0x4980A0`) re-queries isDLC
  and enters on 5, runs the eShop check on 2 (and may enter), opens the deny window
  (`Page+0x370`) on 0, ignores 1 / 3 / 4. `Control_CupButton::setCup` draws 0 and 4
  alike and 2 and 5 alike. The gate therefore returns `NotSale(0)`. Not yet replayed
  in game.
* **Part unlocks, 4.0.1 disassembly (2026-11-04)**: the driver / body / tire / glider
  overloads of `FlagAccessor::isOpen` follow the cup one (`+0x865E7C`) back to back:
  `+0x865F14 / +0x865F60 / +0x865FAC / +0x865FF8`. Same code, different table:
  `save+0x188` -> one byte per id at `+0x1F20` (cups), `+0x1F40` (8 slots, one caller,
  not used), `+0x1F48` drivers, `+0x1F88` bodies, `+0x1FC8` tires, `+0x2008` gliders;
  open means byte == 3 (1 and 2 are earlier stages of the unlock presentation; `+0x866DFC`
  scans the 42-slot body table for the first 2). The mapping comes from the callers: the
  parts-list builder at `+0x474F98` calls the body overload once per body id (41 calls),
  the tire one 22 times and the glider one 15 times, and the loadout sanitiser
  `+0x3FD508` checks a stored loadout's driver (`+0x10`), body (`+0x30`), tire (`+0x40`)
  and glider (`+0x50`) in that order, zeroing any that are not open. Matching
  `get*State` sret getters sit just before them (`+0x865CEC..+0x865E2C`) and are used by
  the coin-unlock / presentation code, not by the select lists. `PartUnlockHook` returns
  true for a closed id the AP state allows (base-game ids only: drivers 0..43, never the
  BCP drivers 44..52). Boot on 4.0.1: all four resolve and install, and the sanitiser
  calls them at save load with x1 = a stack pointer (by-reference ABI, as expected).
  Not yet verified: a received part appearing in the vehicle select on a fresh save.
* **Speed**: by user decision (2026-10-16) the engine-class picker is NOT gated; the
  restriction is the top-speed clamp scaled by Progressive Speed. `engine_max` in the
  state message stays informational.
* **Kart stats** (4.0.1 static analysis, 2026-11-09; `StatCapHook.cpp`). Stat points
  live in four global tables, not in KartVehicle / KartVehicleMove: GOT slot
  `main+0x12F9D98` -> global -> manager, `manager+0xF0` = table object (`tbl+0x20`
  must be non-null). Rows are 14 s32 (0x38 bytes): body `tbl+0x98` (count u16
  `+0xD4`, 41), driver `+0xA0` (`+0xD6`, 53), tire `+0xA8` (`+0xD8`, 22), glider
  `+0xB0` (`+0xDA`, 15); an out-of-range id reads the fallback row at `tbl+0x1B8 /
  0x1F0 / 0x228 / 0x260`. Part ids on KartVehicle: body `+0xB4`, driver `+0xB8`,
  tire `+0xC0`, glider `+0xC4` (`+0xA8` and `+0xB0` both hold the player index, so
  `vehicle::kBodyId/kDriverId` in Structs.hpp are wrong; they only feed logs). Mii
  drivers 0x1D / 0x34 with u32 `v+0xFC <= 2` use driver row `s32[main+0xF242C8 + 4 *
  form]` = {17, 0, 10}. `+0x170738` (single caller `+0x16FA58`, kart setup) sums the
  four rows per column into `KartVehicle+0x2DC + 4 * col` and indexes the per-level
  physics tables with `clamp(sum - 1, 0, 19)`; CPUs (`v+0xD2`) get level 20 on
  several stats. The select screen draws `0.75 + sum / 4` bars (checked on many
  combos). Columns, matched 100% against the community stat sheet: 0 weight,
  1 acceleration, 2 (not in the sheet), 3 traction, 4 mini-turbo, 5..8 speed
  ground / water / anti-gravity / air, 9..12 handling (same order), 13
  invincibility. Ruled out on the way: `KartVehicle+0x78` (per-body/tire chassis
  tuning and the model list).
* **Level tables / base top speed** (4.0.1 static, 2026-11-10). The table object
  also holds 21-entry per-level tables (`tbl+0x28` weight 0xC each, `+0x30`
  accel-ish 8 each, `+0x58/+0x60/+0x68` ground / water / anti-grav speed 2 floats
  each, `+0x70` air 1 float). `+0x170738` copies them into KartVehicleMove (via
  `+0x185F98`, its only caller): speed bases at `Move+0x4B8/4BC` (ground, 0 / 10
  coins), `+0x4C0/4C4` water, `+0x4C8/4CC` anti-grav, `+0x50C` air. Ground runs
  only 7.525/8.025 (level 0) to 8.000/8.500 (level 19), ~6%, so a stat cap alone
  is barely felt; accel runs 0.035 to 0.130. `+0x182C14` (every frame) rebuilds
  the live top `Move+0x420 = lerp(+0x4B8, +0x4BC, coins / 10) * Move+0x4B4`
  (engine factor) and the boost / star speeds as multiples of it, so
  `StatCapHook` scales the seven bases once after the original (verified
  2026-11-10, 200cc, 60%: live top 7.155, highest 8.36 with boosts).
* **Grand Prix result** (4.0.1 static, 2026-11-10; `GpResultHook.cpp`). Points
  table: 12 rows of 12 s32 at `main+0xF739D4` (row = kart count - 1; 12 karts =
  15 12 10 9 8 7 6 5 4 3 2 1); `+0x8703A0` / `+0x8703EC` read it for the
  PlayReport and the results UI. The trophy writer `+0x552FB0(arg, bool* dirty)`
  returns unless `arg[0] == 0`, then for each local player (`arg[0xC]`) takes
  Player = `PlayerManager->ptrs[PlayerManager+0x17C + 4i]` and the head of its
  GP history ring (`Player+0x58` buf, `+0x60` cap, `+0x64` head, `+0x68` count,
  5 u32 per entry): entry[0] = total points (stars: >= 60 three, 57..59 two,
  54..56 one), entry[2] = final placing (1/2/3 -> trophy byte 3/2/1). It stores
  max(old, new) at `save+0x188 -> +0x688 + engine * 0x20 + cup` (stars at
  `+0x588`); `Control_TrophyIcon::setCup` (`+0x479D98`) reads the same bytes.
  The per-race PlayReport has no GP total (its `Points` is online rating).
* Ryujinx itself prints every PlayReport as JSON (`ServicePrepo
  ProcessPlayReport`) in its log, which doubles as a cross-check for the
  mod's MessagePack capture during emulator testing.

## What changed in 4.0.0 (from Ro's port)

Checked against every 3.0.5 / 4.0.0 `source.s` pair on 2026-09-27:

* Code moved by roughly `+0x3A00`; all function addresses differ.
* `object::DriverKart` members shifted by 8 (`0x1AC -> 0x1B4`,
  `0x324 -> 0x32C`, `0x334 -> 0x33C`). Not used by this mod.
* UI page ids shifted by one (`PAGEID_RACE 0x6E -> 0x6F`). Not used.
* A UI struct member moved `0x1744 -> 0x1A44`. Only matters for patterns.
* Register allocation changed inside `gear::ItemOwner::calcKeyInput_`.
  This mod hooks `startSlot` at function entry, where the ABI fixes the
  argument registers, so it is unaffected.
* Unchanged and used here: the scene chain (`+0x1B0` ObjectEngine,
  `+0x218` RaceDirector, `+0x238` KartDirector, `+0xC8` kart holders),
  `RaceKartChecker + 0x40` rank, `RaceInfo + 0x8 / + 0x180`,
  `ItemOwner + 0x48 -> + 0x48 -> KartVehicle + 0xD0` (is local player),
  `startSlot(int, EItemSlot, bool, bool)`.

## Provenance and attribution

* Addresses and pointer chains: commented ASM of
  [RoGamer97/ASM-Cheats-and-Patches](https://github.com/RoGamer97/ASM-Cheats-and-Patches)
  (`Switch/Mario Kart 8 Deluxe/4.0.1/*/source.s`). Those patches are
  CC BY-NC-ND; only addresses and function names are used, no code.
* Porting method: Ro's stream "Porting MK8D patches to v4.0.0 (Tutorial
  and Tips)" (2026-09-25). See `docs/porting-notes.md`.
* Patterns: copied as data from
  [fishguy6564/MK8DX-Base-Plugin](https://github.com/fishguy6564/MK8DX-Base-Plugin)
  `symbols.toml` (GPLv2 repository; none of its code is used). Struct
  offsets in `src/game/Structs.hpp`:
  [fishguy6564/MK8DX-Headers](https://github.com/fishguy6564/MK8DX-Headers).
* The PlayReport IPC hook shape follows the `smbw_ap` project.

## Replacing a pattern with an address

Once a 4.0.1 dump is on disk, any pattern-only entry can be pinned:

1. Boot once and read the resolved offset from the log, or find the
   function in Ghidra / IDA.
2. Add `address = "0x..."` to its entry in `syms/mk8dx_symbols.toml`.
3. `python scripts/gen_symbol_table.py`, rebuild.

`scripts/make_pattern.py` does the reverse (address to unique pattern).
Never commit the dump itself (`*.nso`, `*.text.bin` are gitignored).

## Known gaps

* AP-locked parts the save already owns are still selectable in the menus
  (they are swapped at race start by `KartGuardHook`): the menus are only
  ever opened, never closed (see the part-unlock finding above).
* `EGrandPrixID` is assumed to equal `ECup - 1`; `CupGateHook` logs the
  ids it sees so this can be confirmed on first boot.
* `ui::CourseInfo` carries no course name. Course ids for the hook channel
  are learned by pairing a hook `race_result` with the PlayReport of the
  same race; the PlayReport channel needs no ids at all.
