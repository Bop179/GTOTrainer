# Roadmap

**Focus: 100bb and 200bb cash at 6-max, 8-max and 9-max.** Everything else is out of scope for now (see the end of this file).

## Where things stand (2026-10-30)

| | 100bb | 200bb |
|---|---|---|
| **6-max** | GTO Nexus, up to vs 6-bet. Bet sizes assumed. | GTO Wizard, up to vs 6-bet plus SB-vs-BB limped pots, solver sizes. |
| **8-max** | Built from 9-max GTO Nexus (UTG folded), up to vs 6-bet. Bet sizes assumed. | GTO Wizard, up to vs 6-bet plus SB-vs-BB limped pots, solver sizes. |
| **9-max** | GTO Nexus, up to vs 6-bet. Bet sizes assumed. | GTO Wizard 8-max data once UTG folds, up to vs 6-bet plus limped pots, solver sizes. UTG's spots: GTO Academy, open and vs open only. |

GTO Wizard limits a free account to 100 new spots a day, so the view counts below set how many days each item takes.

## To do, in priority order

### 1. ✅ Limped pots: SB vs BB at 200bb (done 2026-10-30)

At 6-max and 8-max 200bb the SB limps about 40% of its hands. The limp line now plays out: the BB checks or raises, and the hand goes on through the re-raises to the all-in. The 8 → 9 mapping carries it to 9-max 200bb.

- [x] Pulled the line from GTO Wizard: 6 spots at 6-max (raise 3.5, re-raise 18, 4-bet 45, 5-bet 99, then all-in) and 5 at 8-max (3.5, 22, 55, then all-in). 11 views.
- [x] New spot types `FACINGLIMP` and `LIMP_FACING2B` to `LIMP_FACING6B`, a "Limped pot" chip in Settings, and live-table hands where the SB limps.
- [x] Facing a limp, the BB's passive option is labelled Check.
- Caveat: as elsewhere, an all-in in the middle of the line is treated like the raise at that spot, because only the main raise line was pulled.

### 2. ✅ 9-max 200bb: vs 3-bet and beyond from the 8-max data (done 2026-10-30)

9-max with UTG folded plays essentially the same as 8-max. The trainer already uses this to build 8-max from 9-max, so do the reverse at 200bb:

- [x] Map `8max/200bb/*` onto 9-max seats: UTG → UTG1, UTG1 → UTG2, the rest unchanged. Copy `SIZES` too.
- [x] Let the mapped charts replace GTO Academy's for every spot that doesn't involve UTG, so a hand stays on one source and one set of bet sizes. Keep GTO Academy for UTG's opens and for spots facing a UTG open.
- [x] Do the mapping at load time in `index.html`, next to the existing 9 → 8 loop. That way new 8-max nodes, including the limp line from item 1, carry over automatically.
- Caveat: this ignores the card removal of UTG's folded hand, the same small approximation 8-max already makes.

### 3. Real 8-max 100bb from GTO Wizard

- [ ] Pull 8-max 100bb from GTO Wizard. A full tree to vs 6-bet is about 147 spots, so two days. It replaces the 9-max-derived ranges (the derivation loop's `??=` already lets real data win) and brings solver bet sizes.
  - Started 2026-10-30: 25 spots read (every open, and vs open for UTG, UTG1 and LJ openers). They're kept out of the repo until the tree is complete, so a hand doesn't mix the two sources.
  - GTO Wizard's SB limps 44.8% at 8-max 100bb (GTO Nexus never does), so this also needs the limp line, about 5 more spots.

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

- Heads-up.
- Postflop.
