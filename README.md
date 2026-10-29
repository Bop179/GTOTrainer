# GTO Trainer

A preflop trainer for No-Limit Hold'em cash games. You get dealt a hand at a spot, pick an action, and it grades your choice against solver ranges, showing the full strategy mix for that hand and the whole range grid.

## Run it

Open `index.html` in a browser. You don't need to install anything, run a server or be online. Settings and progress are saved in your browser.

## Using it

- **⚙ Settings:** pick the format, stack depth, spot types (Open, vs Open, vs 3-bet, vs 4-bet+) and your positions. Leave the spot types on **Live table** and hands play out like a real table: the other seats act from the same ranges, and the hand continues until it ends or the data runs out.
- **Keys:** `F` fold, `C` call/limp, `R` raise, `A` all-in, `Space` for the next step or hand, `M` to mute.
- **Grading:**
  - ✓ Correct: within 5 points of the solver's most-played action, or played at least 50% of the time.
  - ≈ Acceptable: a mixed action played at least 15% of the time.
  - ✗ Mistake: anything less.
- **Leaks:** shows your mistake types and your worst spot and hand-type combinations, with a **Drill** button for each. Hands you miss come back for review after 3, then 10, 30 and 100 hands.
- **Sound:** nine sound packs and a volume slider, in Settings.

## What's covered

| Format | Stack | Spots |
|---|---|---|
| 6-max | 20bb | open, vs open, vs 3-bet, vs 4-bet |
| 6-max | 50bb | up to vs 5-bet |
| 6-max | 100bb, 200bb | up to vs 6-bet |
| 6-max MTT | 20bb | open, vs open, vs 3-bet |
| 6-max MTT | 40bb | up to vs 5-bet |
| 8-max | 40, 50, 75bb | open, vs open |
| 8-max | 100bb | up to vs 6-bet |
| 8-max | 150, 200bb | up to vs 4-bet |
| 9-max | 40, 50, 75, 150, 200bb | open, vs open |
| 9-max | 100bb | up to vs 6-bet |
| Heads-up | 50, 100bb | up to vs 5-bet |

When a hand reaches a spot that has no data, it ends with "No solver data past this point".

## Data sources

| File | Source | Covers |
|---|---|---|
| `data.js` | GTO Nexus's bundled preflop ranges, built by `build.py` | 6-max 20/50/100bb, 6-max MTT, 9-max 100bb, heads-up |
| `data200.js` | GTO Wizard, 6-max cash 200bb | 6-max 200bb, with GTO Wizard's bet sizes |
| `data8.js` | GTO Wizard, 8-max cash 150bb and 200bb (cEV, 2.5x opens) | 8-max 150/200bb, with GTO Wizard's bet sizes |
| `data9.js` | GTO Academy's free charts | 9-max 40/50/75/150/200bb |

- **8-max** at 40, 50, 75 and 100bb is built from the 9-max data with UTG folded and the remaining seats renamed. This ignores the small card-removal effect of UTG's folded hand.
- **Bet sizes:** the GTO Wizard spots use the solver's own sizes. Everywhere else, the trainer assumes standard sizes:
  - Opens are 2.5bb (2bb at 40bb or less; 3bb from the SB).
  - 3-bets are 3x in position and 4x out of position.
  - 4-bets and later raises are 2.3x.
  - Any raise above 55% of the stack becomes an all-in.

**This ranges data is for personal study only.** It comes from paid or proprietary tools. Please don't copy it outside this repo or share it publicly.

## Files

- `index.html`: the whole app (HTML, CSS and JS in one file).
- `build.py`: rebuilds `data.js` from a GTO Nexus install. Run it with `python3 build.py [path to preflop_ranges_viewer]`.
- `data*.js`: range data. Each row is `[allin, raise, call, fold, reach]` for one of the 169 hands, with reach from 0 to 1.
