# GTO Trainer

A trainer for No-Limit Hold'em cash games. You get dealt a hand at a spot, pick an action, and it grades your choice against solver ranges, showing the strategy mix for that hand and the whole range grid. Preflop covers 6-max, 8-max and 9-max; when a 100bb hand ends heads-up in a solved pot it plays on through the flop, turn and river.

## Run it

Open it online, always the latest version:
- https://bop179.github.io/GTOTrainer/ (GitHub Pages, updates a minute or two after a push)
- https://147-224-143-161.sslip.io/app/ (the solver VM, which pulls the repo every 5 minutes)

Or open `index.html` from a download. Preflop works offline; postflop always needs the VM, and when the VM can't be reached the trainer simply plays preflop only. Settings and progress are saved per browser and per site, so each link (and a downloaded copy) keeps its own.

## Using it

- **⚙ Settings:**
  - **Game, stack and spots:** pick the format, stack depth, spot types (Open, vs Open, Squeeze, Cold 4-bet, vs 3-bet, vs Squeeze, vs Cold 4-bet, vs 4-bet+ and Limped pot; only the types the chosen format and stack have data for are shown) and your positions. Leave the spot types on **All** and hands play out like a real table: the other seats act from the same ranges, and the hand continues until it ends or the data runs out.
  - **Your hand:** only deal the hands you list (`AKs, 88, AQ`).
  - **Streets** (where postflop is solved): Preflop only, Both, or Play to postflop. Play to postflop deals just hands that reach a solved pot and lets you start deciding on the flop, turn or river.
  - **Feedback:** after each decision, or after the hand (no grades until it's played out, then each decision's analysis).
- **Action replay:** before each decision the table plays out what happened since your last action, one seat at a time: folders throw their cards in, bets slide out from the seat. The buttons unlock when it's your turn.
- **Keys:** `1`–`9` pick the action buttons left to right, `Space` or `Enter` for the next step or hand, `Z` takes back your last decision, `M` mutes, `Esc` closes a menu. On a phone, tap the table for the next step.
- **Leaks:** your accuracy, what your mistakes cost, how your style compares with the solver's, and your worst spot and hand-type combinations, with a **Drill** button for each (preflop). A hand you miss comes back for review after 3 hands, then after 10; answer it right twice in a row and it's learned. **Export** and **Import** move your history between browsers.
- **Ranges:** pick any spot at the current format and stack and see its full chart and action mix, without playing a hand. Tap or hover a hand for its exact mix.
- **Sound:** nine sound packs and a volume slider.

## Grading

| | ✓ Correct | ≈ Mixed / Close | ✗ Mistake |
|---|---|---|---|
| **Preflop, spots with the solver's EV** | Loses under 0.05bb against the best action, or the solver plays it 15% of the time or more | Loses under 0.1bb (or under 0.5% of the pot, where that's more), or the solver plays it 5% or more | Anything else |
| **Preflop, other spots** | Within 5 points of the solver's most-played action, or played 50% or more | Played 5% or more | Anything else |
| **Postflop** | Played 25% or more, or 5% or more and within 2% of the pot of the best action | Played 5% or more; or 1% or more and within 5% of the pot; or within 1% of the pot | Anything else |

- The middle grade reads **Mixed** when the solver plays your action 5% of the time or more, and **Close** when it doesn't but the action costs little.
- EV is being added to the preflop spots day by day (ROADMAP item 8), so some spots still grade by frequency.
- Postflop solves stop at about 1% of the pot, so when two or more actions' EVs fall within 1% of the pot of the hand's EV under the solver's mix, they count as tied and all show that mixed EV (Fold 90% at 0 and Call 10% at +0.49bb both show +0.05bb). The raw EVs are under **Show the maths**.
- After a postflop decision you also see your equity against the villain's range, your outs, where your hand sits in your range, what similar hands do, and the EV of every option. **Show the maths** opens the working.

## What's covered

| Format | Stack | Preflop | Postflop |
|---|---|---|---|
| 6-max | 100bb | up to vs 5-bet, plus SB-vs-BB limped pots and multiway: squeezes, overcalls and cold 4-bets, and your replies when you face one | heads-up pots |
| 6-max | 200bb | up to vs 6-bet, plus the same limped pots and multiway spots | not yet |
| 8-max | 100bb | up to vs 6-bet, plus the same limped pots and multiway spots | heads-up pots |
| 8-max | 200bb | up to vs 6-bet, plus the same limped pots and multiway spots | not yet |
| 9-max | 100bb | up to vs 6-bet, plus the same limped pots and multiway spots | heads-up pots once UTG has folded (the 8-max solves) |
| 9-max | 200bb | up to vs 6-bet, plus the same limped pots and multiway spots | not yet |
| Heads-up | 100bb | hidden for now (the data is still in `data.js`; drop `HU` from `HIDDEN_GAMES` in `index.html` to bring it back) | no |

When a hand reaches a spot that has no data, it ends and says why ("No solver data past this point", three players to the flop, a pot that isn't solved). Planned additions are in [ROADMAP.md](ROADMAP.md).

## Data sources

| File | Source | Covers |
|---|---|---|
| `data.js` | GTO Nexus's bundled preflop ranges, built by `build.py` | 9-max 100bb UTG lines, heads-up 100bb (only 100bb and 200bb are built) |
| `data200.js` | GTO Wizard, 6-max cash 200bb | 6-max 200bb, with GTO Wizard's bet sizes |
| `data6.js` | GTO Wizard, 6-max cash 100bb (cEV, 2.5x opens) | 6-max 100bb, with GTO Wizard's bet sizes; replaces GTO Nexus's 6-max 100bb |
| `data8.js` | GTO Wizard, 8-max cash 100bb and 200bb (cEV, 2.5x opens) | 8-max 100/200bb, and 9-max at those stacks, with GTO Wizard's bet sizes |
| `ev.js` | GTO Wizard's per-action EV, built by `build_ev.py` | the preflop spots graded by EV |
| the VM | [postflop-solver](https://github.com/b-inary/postflop-solver) runs on Oracle Cloud (`solver/`) | flop and turn strategies for every solved pot, loaded one piece at a time |

- **9-max** at 100 and 200bb uses the GTO Wizard 8-max data once UTG folds, with UTG1 and UTG2 standing in for 8-max's UTG and UTG1. This ignores the small card-removal effect of UTG's folded hand. At 100bb, UTG's own lines (its open, hands facing its open, and the re-raises after) stay on GTO Nexus's real 9-max solve, with assumed bet sizes. At 200bb there's no 9-max solve, so UTG's lines are estimated from 8-max UTG's, with UTG1 and UTG2 both playing 8-max UTG1. That makes 9-max UTG about one seat too loose there (it opens 13%; GTO Nexus has 9-max UTG at 11% at 100bb).
- GTO Academy's free 8/9-max charts were dropped on 2026-11-01. They were 3 to 13 points tighter than GTO Wizard at every seat, even at seats where 8-max and 9-max have the same players behind (BTN opens 40% vs 47%), and folded hands like A5s from UTG at 200bb. With them went 8-max and 9-max at 40, 50 and 75bb.
- Only 100bb and 200bb are kept (2026-11-02): 6-max 20/50bb, 6-max MTT, heads-up 50bb and 8/9-max 150bb were removed.
- **Bet sizes:** the GTO Wizard spots use the solver's own sizes. Everywhere else, the trainer assumes standard sizes:
  - Opens are 2.5bb (3bb from the SB).
  - 3-bets are 3x in position and 4x out of position.
  - 4-bets and later raises are 2.3x.
  - Any raise above 55% of the stack becomes an all-in.

**The range data is for personal study only.** It comes from paid or proprietary tools, so please don't redistribute it.

## Files

- `index.html`: the app (HTML, CSS and the preflop trainer).
- `postflop.js`: postflop play, grading and feedback. `handclass.js`: hand groups, board texture and showdown equity (`node handclass.js` runs its self-check).
- `river.js` and `river_wasm.js`: the river solver that runs in the browser, loaded on the first postflop hand.
- `data*.js`: range data. Each row is `[allin, raise, call, fold, reach]` for one of the 169 hands, with reach from 0 to 1. `ev.js`: per-action EV for the same rows.
- `build.py`: rebuilds `data.js` from a GTO Nexus install (`python3 build.py [path to preflop_ranges_viewer]`). `build_ev.py`: rebuilds `ev.js` from the daily EV reads.
- `solver/`: the postflop solver wrapper (`src/`), the job builder, queue and splitter that run on the VM, and `test_postways.js` (`node solver/test_postways.js` checks every solved pot against the preflop spots that lead to it).

## Licences

`river_wasm.js` is [postflop-solver](https://github.com/b-inary/postflop-solver) by Wataru Inariba, licensed AGPL-3.0, compiled to WebAssembly through the small wrapper in `solver/src/lib.rs`. Its source is that repository at the revision pinned in `solver/Cargo.lock`, and `solver/build_wasm.sh` rebuilds the file.
