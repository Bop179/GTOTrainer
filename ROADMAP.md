# Roadmap

**Focus: 100bb and 200bb cash at 6-max, 8-max and 9-max.** Everything else is out of scope for now (see the end of this file).

## Where things stand (2026-11-05)

| | 100bb | 200bb |
|---|---|---|
| **6-max** | GTO Wizard, up to vs 5-bet (every 5-bet is all-in) plus SB-vs-BB limped pots and multiway, solver sizes. | GTO Wizard, up to vs 6-bet plus SB-vs-BB limped pots and multiway, solver sizes. |
| **8-max** | GTO Wizard, up to vs 6-bet plus SB-vs-BB limped pots and multiway, solver sizes. | GTO Wizard, up to vs 6-bet plus SB-vs-BB limped pots and multiway, solver sizes. |
| **9-max** | GTO Wizard 8-max data once UTG folds, solver sizes, plus limped pots and multiway. UTG's lines: GTO Nexus, bet sizes assumed. | GTO Wizard 8-max data, up to vs 6-bet plus limped pots and multiway, solver sizes. UTG's lines are estimated from 8-max UTG (about one seat too loose). |

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
- [x] Let the mapped charts replace GTO Academy's for every spot that doesn't involve UTG, so a hand stays on one source and one set of bet sizes. (2026-11-01) UTG's own lines now use 8-max UTG's too, with UTG1 and UTG2 both playing 8-max UTG1, and GTO Academy is gone: its charts were tighter than GTO Wizard's at every seat and folded A5s from UTG at 200bb.
- [x] Do the mapping at load time in `index.html`, next to the existing 9 → 8 loop. That way new 8-max nodes, including the limp line from item 1, carry over automatically.
- Caveat: this ignores the card removal of UTG's folded hand, the same small approximation 8-max already makes.

### 3. ✅ Real 8-max 100bb from GTO Wizard (done 2026-11-01)

- [x] Pulled 8-max 100bb from GTO Wizard over three days (2026-10-30 to 11-01): 134 spots, every open to vs 4-bet, 28 vs 5-bet, the 9 vs 6-bet spots where the 5-bet isn't already all-in, and the 6-spot limp line (3.5, 15, 26.5, 53, all-in). Totals match GTO Wizard's within 0.07pp.
- [x] It replaces the 9-max-derived 8-max ranges. The 9 → 8 derivation now skips any depth that has a real 8-max solve, so no GTO Nexus spot is left over where GTO Wizard has no node.
- GTO Wizard's SB limps 44.8% at 8-max 100bb (GTO Nexus never does), so 8-max and 9-max 100bb now have limped pots too.

### 4. ✅ Solver bet sizes at 100bb (done 2026-11-02)

Only 9-max 100bb UTG lines still use assumed sizes (GTO Nexus files don't include sizes).

- [x] 6-max: pulled 6-max 100bb from GTO Wizard over two days (2026-11-01/02, 70 spots, 70 views) into `data6.js`: every open to vs 4-bet, 15 vs 5-bet, and the limp line (3.5, 14, 29.5, all-in). Every 5-bet is all-in, so there's no vs 6-bet. Same cEV solve as 200bb. Totals match GTO Wizard's within 0.08pp.
- [x] It replaces GTO Nexus's 6-max 100bb ranges entirely, including Nexus's 7 vs 6-bet spots that GTO Wizard has no node for. The SB now limps at 6-max 100bb too.
- [x] 9-max (done 2026-11-01, with item 3): item 2's mapping now runs at 100bb too, so 9-max non-UTG spots use GTO Wizard's ranges and sizes. UTG's lines keep GTO Nexus's real 9-max solve, with assumed sizes. GTO Wizard's 9-max is Premium only.

### 5. ✅ Multiway spots (6-max done 2026-11-02, 8-max and 9-max 2026-11-05)

Squeezes (facing an open plus a call), overcalls, BB vs open + call, and cold 4-bets (facing an open and a 3-bet). GTO Wizard's cash solves include them because they're solved with cold calls.

- [x] Key format: `game/stack/OPENER+OTHER/hero/NODE`, with `FACINGRFI_CALL` (OTHER called the open) and `FACING3B_COLD` (OTHER 3-bet it). The trainer splits the villain field on `+`.
- [x] Pulled 6-max 100bb and 200bb: 20 squeeze/overcall and 20 cold 4-bet spots each (80 views), every opener, caller/3-bettor and hero seat. Totals match GTO Wizard's within 0.05pp. GTO Wizard gives no cold-call option facing an open and a 3-bet, so those spots are 4-bet or fold.
- [x] Trainer: two new spot types ("vs Open + call", "vs Open + 3-bet", shown only where the data has them), the table replays the open and the call or 3-bet, and solver sizes carry through.
- [x] Live table: players between the opener and you now act from their own spots, so you face an open plus a call or 3-bet when they do. A line that brings in a third player, or one with no data, redeals. After you call or 3-bet an open, and after a call or 3-bet of your open, the players behind act from the multiway spots; a squeeze or cold 4-bet there ends the hand ("No solver data past this point").
- [x] 8-max 100bb (2026-11-04): 112 GTO Wizard spots (56 open + call, 56 open + 3-bet) in `data8.js`; 9-max 100bb gets them through the 8 → 9 mapping.
- [x] 8-max 200bb (2026-11-05): 112 GTO Wizard spots in `data8.js`, carried to 9-max 200bb by the 8 → 9 mapping.
- [x] The 8 → 9 mapping splits `OPENER+OTHER` (2026-11-02), so 9-max gets these spots as soon as 8-max has them. Tested with stand-in data: 80 8-max spots became 120 at 9-max (at 9-max UTG spots are borrowed for both UTG1 and UTG2), and live hands ran clean.
- Not covered: more than two players in front of you. Squeezes of your open and the replies to your squeeze or cold 4-bet are item 6.

### 6. ✅ Squeezes and cold 4-bets against you, and replies to yours (done 2026-11-11)

Four more GTO Wizard nodes per line, read after the players behind the raiser fold:

| Node | Key | Spot |
|---|---|---|
| `FACINGSQZ` | `CALLER+SQUEEZER/opener` | You open, one player calls, another squeezes. The caller is still behind you. |
| `FACINGSQZ_CALLER` | `OPENER+SQUEEZER/caller` | You call an open, someone squeezes, the opener folds. |
| `FACINGC4B` | `3BETTOR+4BETTOR/opener` | You open, get 3-bet, and someone cold 4-bets. The 3-bettor is still behind you. |
| `FACINGC4B_3B` | `OPENER+4BETTOR/3-bettor` | You 3-bet an open, someone cold 4-bets, the opener folds. |

The same nodes give the villains' answers when you squeeze or cold 4-bet: the opener answers first, then, if the opener folds, the caller or 3-bettor. Up to 56 nodes per type at 8-max (224 views per stack) and 20 at 6-max (80 views per stack), so about 6 days of the free quota in all.

- [x] Trainer: spot types "vs Squeeze" and "vs Cold 4-bet"; the live table plays these lines and ends the hand only where the data stops. Walker stages 9 to 12 in `.claude/gw_walker.js`, appended to the data file with `.claude/gw_append.py`.
- [x] 8-max 200bb: all four done, 224 spots (2026-11-06 to 11-07).
- [x] 8-max 100bb: all four done, 224 spots (2026-11-07 to 11-09).
- [x] 6-max 200bb: all four done, 80 spots (2026-11-10).
- [x] 6-max 100bb: all four done, 80 spots (2026-11-11).
- Not covered: your answer after the opener 4-bets your squeeze (or 5-bets your cold 4-bet), and lines where a player behind the raiser comes in too.

### 7. ✅ Range browser (done 2026-11-06)

- [x] A **Ranges** button opens any spot's chart and whole-range mix at the current game and stack, without playing a hand.

### 8. Grade by how much a mistake costs (after item 6)

Grading now goes by how often the solver plays your action. Grading by EV loss would mark a 0% action that loses almost nothing as close, and a cheap-looking fold that throws away a lot as a big mistake.

- GTO Wizard's free tier shows EV (checked 2026-11-06): the grid's display menu has Strategy, Strategy + EV, EV, Compare EV, Range and All, and the Hands panel lists each action's EV per combo.
- [ ] Find the cheapest way to read per-action EV for all 169 hands (Compare EV mode, the Table tab, or the Hands panel) and add it to the walker. Non-Strategy modes put text in the grid cells and break the current reader, so it needs its own pass.
- [ ] Re-read every node with EV: 1,352 nodes (8-max 100bb 470, 8-max 200bb 488, 6-max 100bb 190, 6-max 200bb 204), about 15 days of the free quota. Daily pull started 2026-11-12, in that order.
- [ ] Trainer: add the EV to each spot's rows and grade by EV lost against the best action (thresholds to pick). The feedback lists every action available with its EV in bb, signed (+ is a gain, - a loss, fold is 0), marks the best one, and shows your pick's EV and its gap to the best ("Call +1.2bb, 0.4bb less than 3-bet +1.6bb").

## Out of scope for now

You can do these later, but they don't come before the items above:

- Heads-up.
- Postflop.
