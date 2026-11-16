# Public Spot Solver Implementation Plan

> Implemented inline with a fresh code review.

**Goal:** Add instant saved-flop lookup and public custom heads-up postflop solving.
**Architecture:** Reuse the existing VM index and binary pieces for saved solutions. A loopback Python API runs one bounded native solve at a time for custom inputs. Caddy proxies /solve/. No access key or login.
**Tech stack:** Existing Rust postflop-solver, Python standard library, vanilla JavaScript.
**Local design:** SPEC.md, intentionally ignored by Git.

## Completed work
- [x] Harden native card/range/size parsing; export only starting-street decisions for custom solves, retaining raw reach precision. Preserve existing batch defaults and bundled river WASM.
- [x] Public API with random 128-bit job IDs, one active job, 12 GB compressed tree cap, 30-minute deadline, 15 GB available-RAM guard, and 14 GB service memory limit without swap.
- [x] At most 32 retained results, expired after two hours or evicted oldest-first for new submissions. Cancellation reaps the native process; service restart clears temporary results.
- [x] Custom form, polling/reconnect, cancellation, weighted range chart, combination EVs, action navigation and immutable submitted-input snapshot.
- [x] Saved-flop selectors by game/stack/matchup; entered-board coverage check including suit and card-order equivalence. Reuse loadPiece, remap displayed combinations, explicitly label the source ranges. Refresh revalidates the index.
- [x] Separate saved/custom result state; changed lookup inputs discard stale results. Trainer hotkeys do not fire in the dialog.
- [x] Deploy isolated service/Caddy route, document limits, validate desktop/mobile UI and real HTTPS solves.

## Verification and review
- Rust: malformed inputs, starting-street traversal and tiny weighted ranges; three tests passed locally and on the server.
- API: public access, validation, capacity, idempotent requests, results, cancellation, timeout, memory guard and retained-result eviction; seven tests passed.
- JS: input/grouping/weighted mixes/terminal paths, suit-equivalent and absent flops, reconnect, saved-input identity, disconnected and expired jobs.
- Existing checks: all 966 scenario mappings and handclass self-check passed.
- Real HTTPS: river and small flop completed; representative 100bb BTN-vs-BB flop accepted and cancelled. Public health and custom solves worked without credentials.
- Browser: saved strategy loaded with zero custom-job requests; action traversal and absent-flop message verified; public custom river completed; mobile dialog had no horizontal overflow.
- Fresh review findings fixed: small reach rounded to zero, missing submitted range context, retained jobs blocking public admission, and stale cached coverage on Refresh. Regression tests were observed failing before the corresponding logic fixes.

## Limits
Full flop solving is not instant; only saved lookup avoids computation. Custom jobs share one server slot. Starting-street exploration only; later streets require a new custom spot. The full representative flop was cancelled after confirming admission, not benchmarked to convergence.
