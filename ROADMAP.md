# Roadmap

**Focus: 100bb and 200bb cash at 6-max, 8-max and 9-max.** Everything else is out of scope for now (see the end of this file).

## Where things stand (preflop 2026-11-05; postflop, item 9, 2026-11-15)

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

### 8. Show every action's EV (gain or loss) and grade by it

Grading now goes by how often the solver plays your action. Grading by EV loss would mark a 0% action that loses almost nothing as close, and a cheap-looking fold that throws away a lot as a big mistake.

- GTO Wizard's free tier shows EV (checked 2026-11-06): the grid's display menu has Strategy, Strategy + EV, EV, Compare EV, Range and All, and the Hands panel lists each action's EV per combo.
- [x] Find the cheapest way to read per-action EV for all 169 hands. Done 2026-11-13: the page's own store already holds every action's strategy and EV for all 169 hands, one view per node, whatever the grid display mode. It matched the Hands panel and the old grid reads (within 0.05pp).
- [ ] Re-read every node with EV: 1,352 nodes (8-max 100bb 470, 8-max 200bb 488, 6-max 100bb 190, 6-max 200bb 204), about 15 days of the free quota. Daily pull started 2026-11-12. Reordered 2026-11-14: 6-max 100bb and 200bb next, then the rest of 8-max 100bb (196 of 470 read), then 8-max 200bb.
  - 8-max 100bb: 196 of 470 (2026-11-14).
  - 6-max 100bb: 100 of 190 (2026-11-15).
- [ ] Trainer: add the EV to each spot's rows and grade by EV lost against the best action (thresholds to pick).
  - Live for every node read so far (2026-11-14): `build_ev.py` packs `.claude/gw*_ev.json` into `ev.js` (re-run after each pull), and 9-max shares 8-max's EV. Grade: under 0.05bb lost correct, under 0.5bb acceptable, else mistake; spots without EV still grade by frequency. Each button shows its EV. Known noise: in BB vs the SB's 5-bet to 53 in a limped pot (rarely reached), the solver mixes calls its own EV puts 1-2.8bb behind folding, so those calls grade as mistakes. The feedback lists every action available with its EV in bb, signed (+ is a gain, - a loss, fold is 0), marks the best one, and shows your pick's EV and its gap to the best ("Call +1.2bb, 0.4bb less than 3-bet +1.6bb").

### 9. Postflop: every heads-up pot at 6-max and 8-max, 100bb and 200bb (started 2026-11-13)

Postflop covers heads-up pots only; 9-max reuses the 8-max solves. The flop and turn are pre-solved on Oracle Cloud; the river is solved live in the browser.

**Spots** (`solver/make_jobs.py`, header lists names and range sources):
- Every heads-up pot type at 6-max (`data6.js`, `data200.js`) and 8-max (`data8.js`), at 100bb then 200bb: 570 scenarios.
- Pot types:
  - single-raised;
  - 3-bet and 4-bet pots;
  - SB-vs-BB limped and limp-raised pots;
  - squeeze and cold 4-bet pots that end heads-up (the opener folds).
- Pots are ranked by how often they happen.
- Flops (of the 1,755 distinct ones, sampled so each texture shows up about as often as it's dealt):

  | Pots | Flops |
  |---|---|
  | The six common 6-max 100bb single-raised pots (BTN, CO, SB, HJ, UTG v BB; BTN v SB) | 183 |
  | Other pots at 5% or more of a game's single-raised pots, and every 3-bet, 4-bet, squeeze and cold 4-bet pot | 95 |
  | Rarer single-raised pots | 40 |

  The trainer deals only solved flops.
- Each spot assumes the players behind fold. When the opener calls a squeeze or cold 4-bet the pot could go 3-way, so that line isn't solved.

**Solves:**
- Sizes:
  - flop 33% and 75%;
  - turn 75% and 125%;
  - river 75% in the pre-solve (the live river uses 33/75/125%);
  - 2.5x raises;
  - all-in once the stack is 1.5x the pot.
  - Limped pots use flop 33/75%, turn and river 75%, 3x raises, so they fit in memory.
- Each solve stops at 1% of the pot exploitability or 1,000 iterations.
- Every flop decision and every turn decision is kept, raised flops included (since 2026-11-14).
- Every hand at every node is kept (`"min_reach": 0`, since 2026-11-15). The solver works out a strategy and EV for a hand even where its line never brings it, so a hand that left the line is still graded.
- Largest trees: 100bb 19.8 GB, 200bb 22.5 GB (limped pot). Trees over 16 GB are compressed automatically, so all fit in 12 GB.

**Machines and cost:**
- gto-vm: Always Free A1, 4 OCPU / 24 GB, 150 GB data volume. It serves the pieces.
- gto-worker: 60 OCPU / 360 GB on the $300 trial credits, from 2026-11-13. It runs 15 solves at once and syncs results to gto-vm every minute.
- The free A1 allowance is 3,000 OCPU-h and 18,000 GB-h per calendar month, pooled across instances, and gto-vm alone uses nearly all of it. So the worker must be gone before December:
  - it powers itself off on 2026-11-30 at 17:00 UTC;
  - the Mac's launchd runs `solver/worker_down.sh` the same day, which terminates it and restores the free-only quota.
- Expected spend: about $100 of credits.
- Disk guards:
  - under 10 GB free on /data, the worker is powered off (`~/worker_sync.sh`);
  - under 8 GB, `run_queue.sh` stops.

**Storage** (`solver/split.py`, 2026-11-15):
- Each flop is cut into a flop piece and one piece per turn card. Pieces are gzipped binary: strategy 1 byte, EV 4 bytes, hands as card indices.
- Turns in suits the flop doesn't have are stored once and suit-swapped on load (verified identical).
- Raw results are truncated to empty markers, with their mtime kept, once split.
- A single-raised flop takes about 12 MB with every hand kept, down from 36 MB (raw copy plus base64 pieces).
- Expected total: about 123 GB of the 147 GB volume.

- [x] Solver wrapper, job builder, queue runner (parallel claims, `REVERSE=1` on gto-vm so both machines follow the order from opposite ends), restart after a reboot.
- [x] River solver in the browser (2026-11-13): `river.js` and `river_wasm.js`, the same solver in WebAssembly. Under 0.1 s and 150 MB for a worst-case river; matches the native solver. Rebuild with `solver/build_wasm.sh`.
- [x] Caddy on gto-vm serves `~/post` at `https://147-224-143-161.sslip.io/` (443 only, no directory listing, `Access-Control-Allow-Origin *` so `file://` can fetch). Cron re-splits every 10 minutes.
- [x] Compact storage and suit-swapped turns (2026-11-15).
- [x] Postflop in the live hand (`postflop.js`): when preflop ends heads-up in a solved pot, the hand goes on to the flop.
  - The villain's hand is drawn from their flop range, and they play by sampling their strategy. The river is solved live from both players' turn ranges.
  - Grading: frequency first, EV second.
    - Correct: played 25%+, or 5%+ within 2% of the pot.
    - Acceptable: 5%+; or 1%+ within 5% of the pot; or under 1% within 1% of the pot.
    - Otherwise a mistake.
  - Feedback:
    - your hand and draws, and the board texture;
    - the price to call, and your equity against villain's current range (exact, every runout);
    - outs;
    - where your hand ranks in your range;
    - the mix for hands like yours;
    - every action's EV, the whole range's mix, and a 13x13 chart.
  - **Play to postflop** deals only spots that lead into a solved pot. **Start deciding on** Flop / Turn / River plays your earlier streets by the solver's strategy, skipping its fold when it has another line.
  - A hand off the solver's line plays on ungraded (whole-range mix on the buttons) instead of ending. Once the re-solve is done, only a hand that was never in the flop range stays ungraded until the river.
  - Showdowns name the winner. Every ending other than your fold says why (multiway, unsolved pot, game or stack without postflop).
  - Check: `node solver/test_postways.js` (every scenario's spots exist, are found from the preflop line, and put in the solved pot).
- [ ] Pre-solve everything (100bb re-solve with every hand from 2026-11-15 01:15Z, then 200bb): 51,158 solves, about 87 h on the worker, done around 2026-11-19. Progress: dashboard `solver/dashboard.py` (`ssh -N -L 8080:localhost:8080 gto-vm`).
- [ ] Open TCP 443 to other users: ingress rule in the OCI security list, and `iptables -I INPUT 6 -p tcp --dport 443 -j ACCEPT` + `netfilter-persistent save` on the VM. Egress is free up to 10 TB a month.
- [ ] Postflop hands in the leak log and reviews.
- [ ] Maybe: grade a hand that was never in the flop range (a preflop misplay) as the closest hand that is, marked approximate.

**Preflop, done alongside (2026-11-14/15):**
- A hand the solver never brings to a spot plays it ungraded instead of ending.
- A called all-in runs out to a showdown, with your equity against the calling range:
  - over a single raise, only re-raises call a shove;
  - calling an all-in goes to the showdown against the range that shoved.
- Re-raising a squeezer or cold 4-bettor gets a reply, from that seat's 3-bet-facing-a-4-bet spot.

## Out of scope for now

Might do these later, might never do these:

- Postflop multiway pots (3 or more players on the flop; decided 2026-11-13). postflop-solver is heads-up only, and 3-way trees would not fit on the VM.
