# Porting notes (3.0.5 research to 4.0.0)

Summary of the method in Ro's stream "Porting MK8D patches to v4.0.0
(Tutorial and Tips)" (youtube.com/watch?v=9SUvZHHfOEc, 2026-09-25), and how
this repo applies it. Written from the auto-generated subtitles; hex values
were cross-checked against the published `4.0.0/` patch sources, not taken
from the captions.

## The method

1. **Build id.** Every game update changes it. It is at offset `0x40` of
   the decompressed `main`. 4.0.0 is `2C336A9BCF79C3040CE506CDD391B578`,
   4.0.1 is `158C0C7399AABD7BF83795C2EF3484C7`.
2. **Find the same code in the new binary.** Copy a run of instruction
   bytes around the old address and search for them in the new `main`.
   Unchanged functions are byte-identical apart from their address.
3. **Never include relative instructions in the search bytes.** `BL`, `B`
   and `ADRP` encode a distance, and distances change whenever code is
   inserted anywhere between the two ends.
4. **If a search finds several hits,** search for a neighbouring function
   that is easier to identify and navigate from there.
5. **Re-assemble anything relative at its new address.** A hook's own `BL`
   back into the game must be recomputed for the new location.
6. **Expect struct members to have moved.** A search that includes a
   load/store with a member offset can miss for that reason alone, and code
   that reads the member must use the new offset.
7. **Expect registers to change** inside functions that were recompiled.
   Mid-function hooks that borrow a "free" register must re-check it.
8. **Test every port in game.** Several ports in the stream built fine and
   crashed or silently misbehaved because one call or offset was stale.
9. An automatic patch porter (a web tool that takes both `main` files) does
   steps 2 to 5 for simple patches. It does not know about step 6 or 7.

## How this repo applies it

| Step | Here |
|---|---|
| 1 | `PatternResolver` pins the 4.0.1 build id and refuses any other build |
| 2, 3, 6 | the relaxed pattern pass wildcards exactly those fields (branch and ADRP distances, member-offset immediates) and demands a unique match |
| 4 | ambiguous matches are rejected, never guessed |
| 5 | not needed: hooks are LibHakkun trampolines at function entry, computed at runtime |
| 7 | not needed for the same reason: at function entry the ABI fixes the argument registers |
| 8 | README "First run checklist"; every hook logs what it saw |

## 4.0.0 specifics observed in the stream and the sources

See `docs/symbols.md`, section "What changed in 4.0.0".

Ro expected Nintendo to ship a 4.0.1 shortly after 4.0.0 because 4.0.0
broke some online behaviour, and it did. This repo targets only the latest
update (4.0.1 since 2026-10-21) by decision; a different build makes the
mod inactive rather than half-working.

## 4.0.0 to 4.0.1

The same method, much smaller: Ro published 4.0.1 versions of every patch,
and with addresses masked the `source.s` files are identical to the 4.0.0
ones. The six address-located symbols were moved to Ro's 4.0.1 addresses
(for `onFakeGoal` and `SetRandomCPU`, Ro's hook address minus the unchanged
hook offset); the pattern-located ones needed no change. See
`docs/symbols.md`, section "What changed in 4.0.1".
