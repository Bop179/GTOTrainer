# Roadmap

**Focus: 100bb and 200bb cash at 6-max, 8-max and 9-max.** Everything else is out of scope for now (see the end of this file).

## Where things stand (2026-10-29)

| | 100bb | 200bb |
|---|---|---|
| **6-max** | GTO Nexus, up to vs 6-bet. Bet sizes assumed. | GTO Wizard, up to vs 6-bet, solver sizes. Limped pots missing. |
| **8-max** | Built from 9-max GTO Nexus (UTG folded), up to vs 6-bet. Bet sizes assumed. | GTO Wizard, up to vs 4-bet, solver sizes. vs 5-bet/6-bet pull scheduled for 2026-10-30. Limped pots missing. |
| **9-max** | GTO Nexus, up to vs 6-bet. Bet sizes assumed. | GTO Academy, open and vs open only. Bet sizes assumed. |

GTO Wizard limits a free account to 100 new spots a day, so the view counts below set how many days each item takes.

## To do, in priority order

### 1. Limped pots: SB vs BB at 200bb

At 6-max and 8-max 200bb, the SB limps about 40% of its hands. Right now a SB limp ends the hand, and in live-table mode a villain's limp redeals, so the BB never gets to practise facing a limp. GTO Nexus never limps at 100bb, so 100bb isn't affected.

- [ ] Pull the limp line from GTO Wizard for 6-max 200bb and 8-max 200bb. That's about 3–5 spots per format: BB vs limp, SB vs the BB's raise, BB vs the SB's re-raise, and any spot after that. The limp is `C` in `preflop_actions`, e.g. `F-F-F-F-F-F-C` for the 8-max BB.
- [ ] Add spot types for the limp line to the trainer. That touches `situation()`, `LINES`/`sizing()`, `chainOf()`/`simNext()` (including the limp → redeal in live-table mode), `SPOT_TYPES`, `spotName()` and the keyboard keys.
- [ ] Facing a limp, the BB's options are check or raise, not fold. GTO Wizard draws check in the same green as call, so label it Check in that spot.

### 2. 9-max 200bb: vs 3-bet and beyond from the 8-max data (no views needed)

9-max with UTG folded plays essentially the same as 8-max. The trainer already uses this to build 8-max from 9-max, so do the reverse at 200bb:

- [ ] Map `8max/200bb/*` onto 9-max seats: UTG → UTG1, UTG1 → UTG2, the rest unchanged. Copy `SIZES` too.
- [ ] Let the mapped charts replace GTO Academy's for every spot that doesn't involve UTG, so a hand stays on one source and one set of bet sizes. Keep GTO Academy for UTG's opens and for spots facing a UTG open.
- [ ] Do the mapping at load time in `index.html`, next to the existing 9 → 8 loop. That way new 8-max nodes, including the limp line from item 1, carry over automatically.
- Caveat: this ignores the card removal of UTG's folded hand, the same small approximation 8-max already makes.

### 3. Real 8-max 100bb from GTO Wizard

- [ ] Pull 8-max 100bb from GTO Wizard. A full tree to vs 6-bet is about 147 spots, so two days. It replaces the 9-max-derived ranges (the derivation loop's `??=` already lets real data win) and brings solver bet sizes.

### 4. Solver bet sizes at 100bb

All three formats at 100bb use assumed sizes, because the GTO Nexus files don't include sizes.

- [ ] 6-max: pull 6-max 100bb from GTO Wizard (about 150 spots, two days) and replace the GTO Nexus ranges, so the ranges and sizes come from the same solve. First check which rake settings the free tier offers at 100bb; the free 200bb solve is cEV.
- [ ] 9-max: GTO Wizard's 9-max is Premium only. Once item 3 is done, apply item 2's mapping at 100bb too. That gives 9-max non-UTG spots GTO Wizard's sizes; UTG spots keep GTO Nexus.

### 5. Multiway spots

None of these are in the trainer yet: squeezes (facing an open plus a call), cold 4-bets (facing an open and a 3-bet), overcalls, and BB vs open + call. GTO Wizard's cash solves include them because they're solved with cold calls.

- [ ] Design a key format for spots with more than one villain. Today it's `game/stack/villain/hero/NODE`.
- [ ] Pull the spots: dozens per format and stack, so several days each.
- [ ] Teach the trainer's table view, sizing and hand chaining about extra players.

This is the biggest item by far. Do it last.

## Out of scope for now

You can do these later, but they don't come before the items above:

- Other stacks: 20, 40, 50, 75, 125, 150, 175, 250 and 300bb. This includes the 5-bet/6-bet spots and limped pots at 8-max 150bb.
- Heads-up, MTT and other game variants.
- Postflop.
