# GTO Trainer

A preflop trainer for No-Limit Hold'em cash games. You get dealt a hand at a spot, pick an action, and it grades your choice against solver ranges, showing the full strategy mix for that hand and the whole range grid.

## Run it

Open `index.html` in a browser. You don't need to install anything, run a server or be online. Settings and progress are saved in your browser.

## Using it

- **⚙ Settings:** pick the format, stack depth, spot types (Open, vs Open, vs 3-bet, vs 4-bet+, Limped pot, and at 6-max 100/200bb vs Open + call and vs Open + 3-bet) and your positions. Leave the spot types on **Live table** and hands play out like a real table: the other seats act from the same ranges, and the hand continues until it ends or the data runs out.
- **Action replay:** before each decision the table plays out what happened since your last action, one seat at a time: folders throw their cards in, bets slide out from the seat. The buttons unlock when it's your turn.
- **Keys:** `F` fold, `C` call/check/limp, `R` raise, `A` all-in, `Space` for the next step or hand, `M` to mute.
- **Grading:**
  - ✓ Correct: within 5 points of the solver's most-played action, or played at least 50% of the time.
  - ≈ Acceptable: a mixed action played at least 15% of the time.
  - ✗ Mistake: anything less.
- **Leaks:** shows your mistake types and your worst spot and hand-type combinations, with a **Drill** button for each. Hands you miss come back for review after 3, then 10, 30 and 100 hands.
- **Sound:** nine sound packs and a volume slider, in Settings.

## What's covered

| Format | Stack | Spots |
|---|---|---|
| 6-max | 100bb | up to vs 5-bet, plus SB-vs-BB limped pots and multiway: squeezes, overcalls and cold 4-bets |
| 6-max | 200bb | up to vs 6-bet, plus SB-vs-BB limped pots and multiway: squeezes, overcalls and cold 4-bets |
| 8-max | 100bb | up to vs 6-bet, plus SB-vs-BB limped pots |
| 8-max | 200bb | up to vs 6-bet, plus SB-vs-BB limped pots |
| 9-max | 200bb | up to vs 6-bet, plus SB-vs-BB limped pots |
| 9-max | 100bb | up to vs 6-bet, plus SB-vs-BB limped pots |
| Heads-up | 100bb | up to vs 5-bet |

When a hand reaches a spot that has no data, it ends with "No solver data past this point". Planned additions are in [ROADMAP.md](ROADMAP.md).

## Data sources

| File | Source | Covers |
|---|---|---|
| `data.js` | GTO Nexus's bundled preflop ranges, built by `build.py` | 9-max 100bb UTG lines, heads-up 100bb (only 100bb and 200bb are built) |
| `data200.js` | GTO Wizard, 6-max cash 200bb | 6-max 200bb, with GTO Wizard's bet sizes |
| `data6.js` | GTO Wizard, 6-max cash 100bb (cEV, 2.5x opens) | 6-max 100bb, with GTO Wizard's bet sizes; replaces GTO Nexus's 6-max 100bb |
| `data8.js` | GTO Wizard, 8-max cash 100bb and 200bb (cEV, 2.5x opens) | 8-max 100/200bb, and 9-max at those stacks, with GTO Wizard's bet sizes |

- **9-max** at 100 and 200bb uses the GTO Wizard 8-max data once UTG folds, with UTG1 and UTG2 standing in for 8-max's UTG and UTG1. This ignores the small card-removal effect of UTG's folded hand. At 100bb, UTG's own lines (its open, hands facing its open, and the re-raises after) stay on GTO Nexus's real 9-max solve, with assumed bet sizes. At 200bb there's no 9-max solve, so UTG's lines are estimated from 8-max UTG's, with UTG1 and UTG2 both playing 8-max UTG1. That makes 9-max UTG about one seat too loose there (it opens 13%; GTO Nexus has 9-max UTG at 11% at 100bb).
- GTO Academy's free 8/9-max charts were dropped on 2026-11-01. They were 3 to 13 points tighter than GTO Wizard at every seat, even at seats where 8-max and 9-max have the same players behind (BTN opens 40% vs 47%), and folded hands like A5s from UTG at 200bb. With them went 8-max and 9-max at 40, 50 and 75bb.
- Only 100bb and 200bb are kept (2026-11-02): 6-max 20/50bb, 6-max MTT, heads-up 50bb and 8/9-max 150bb were removed.
- **Bet sizes:** the GTO Wizard spots use the solver's own sizes. Everywhere else, the trainer assumes standard sizes:
  - Opens are 2.5bb (3bb from the SB).
  - 3-bets are 3x in position and 4x out of position.
  - 4-bets and later raises are 2.3x.
  - Any raise above 55% of the stack becomes an all-in.

**This ranges data is for personal study only.** It comes from paid or proprietary tools. Please don't copy it outside this repo or share it publicly.

## Files

- `index.html`: the whole app (HTML, CSS and JS in one file).
- `build.py`: rebuilds `data.js` from a GTO Nexus install. Run it with `python3 build.py [path to preflop_ranges_viewer]`.
- `data*.js`: range data. Each row is `[allin, raise, call, fold, reach]` for one of the 169 hands, with reach from 0 to 1.
