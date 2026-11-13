// Shared by gto-solve (the VM queue, multithreaded) and river.wasm (the trainer's live river solves, single-threaded),
// so both dump nodes in the same format.
// job: {"oop": range, "ip": range, "board" (or "flop"): "Td9d6h" | "Td9d6h2c" | "Td9d6h2c5s", "pot": 5.5, "stack": 97.5,  (bb)
//       "flop_sizes"/"turn_sizes"/"river_sizes": [bets, raises] (only the streets the tree reaches are needed),
//       "target": 0.01 (exploitability, fraction of pot), "max_iter": 1000}
// range: a range string ("AA,AKs:0.5") or per-combo weights ({"AhKh": 0.4, ...}).
// nodes: {"<key>": node}, key tokens = action indices and dealt cards, e.g. "0-1-Kh-0-2" = check, bet, turn Kh, check, bet 2.
//        node = {"player": 0 OOP | 1 IP, "actions": ["Check","Bet 1.8",...], "hands": ["AhKh",...],
//                "reach": [normalized reach per hand], "strat": [[% per hand] per action], "ev": [[bb per hand] per action]}
use postflop_solver::*;
use serde_json::{json, Map, Value};

pub const CHIPS: f64 = 20.0; // chips per bb (the solver works in integers)

fn sizes(j: &Value, k: &str) -> Result<BetSizeOptions, String> {
    match j[k].as_array() {
        Some(a) => BetSizeOptions::try_from((a[0].as_str().unwrap_or(""), a[1].as_str().unwrap_or(""))),
        None => Ok(BetSizeOptions::default()), // a street this tree never reaches
    }
}

fn range(v: &Value) -> Result<Range, String> {
    if let Some(s) = v.as_str() { return s.parse(); }
    let mut r = Range::new();
    for (combo, w) in v.as_object().ok_or("range must be a string or {combo: weight}")? {
        let (a, b) = (card_from_str(&combo[..2])?, card_from_str(&combo[2..])?);
        r.set_weight_by_cards(a, b, w.as_f64().ok_or("weight must be a number")? as f32);
    }
    Ok(r)
}

pub fn game(j: &Value) -> Result<PostFlopGame, String> {
    let board = j["board"].as_str().or(j["flop"].as_str()).ok_or("board missing")?;
    if ![6, 8, 10].contains(&board.len()) { return Err(format!("board {board:?} must be 3, 4 or 5 cards")); }
    let card = |i: usize| if board.len() > i { card_from_str(&board[i..i + 2]) } else { Ok(NOT_DEALT) };
    let f = |k: &str| j[k].as_f64().ok_or(format!("{k} missing"));
    let card_config = CardConfig {
        range: [range(&j["oop"])?, range(&j["ip"])?],
        flop: flop_from_str(&board[..6])?, turn: card(6)?, river: card(8)?,
    };
    let (fl, tu, ri) = (sizes(j, "flop_sizes")?, sizes(j, "turn_sizes")?, sizes(j, "river_sizes")?);
    let tree = TreeConfig {
        initial_state: match board.len() { 6 => BoardState::Flop, 8 => BoardState::Turn, _ => BoardState::River },
        starting_pot: (f("pot")? * CHIPS).round() as i32,
        effective_stack: (f("stack")? * CHIPS).round() as i32,
        rake_rate: 0.0, rake_cap: 0.0, // GTO Wizard preflop data is cEV, no rake
        flop_bet_sizes: [fl.clone(), fl], turn_bet_sizes: [tu.clone(), tu], river_bet_sizes: [ri.clone(), ri],
        turn_donk_sizes: None, river_donk_sizes: None,
        add_allin_threshold: 1.5, force_allin_threshold: 0.15, merging_threshold: 0.1,
    };
    PostFlopGame::with_config(card_config, ActionTree::new(tree)?)
}

/// Iterate until exploitability <= job "target" (fraction of pot) or "max_iter". Returns (iterations, exploitability / pot).
pub fn solve(g: &mut PostFlopGame, j: &Value) -> (u32, f64) {
    let pot = g.tree_config().starting_pot as f32;
    let target = pot * j["target"].as_f64().unwrap_or(0.01) as f32;
    let max_iter = j["max_iter"].as_u64().unwrap_or(1000) as u32;
    let (mut it, mut ex) = (0, f32::MAX);
    while it < max_iter {
        solve_step(g, it); it += 1;
        if it % 10 == 0 { ex = compute_exploitability(g); if ex <= target { break; } }
    }
    if ex == f32::MAX { ex = compute_exploitability(g); }
    finalize(g);
    (it, (ex / pot) as f64)
}

fn act(a: &Action) -> String {
    let bb = |x: &i32| (*x as f64 / CHIPS * 100.0).round() / 100.0;
    match a {
        Action::Fold => "Fold".into(), Action::Check => "Check".into(), Action::Call => "Call".into(),
        Action::Bet(x) => format!("Bet {}", bb(x)), Action::Raise(x) => format!("Raise {}", bb(x)),
        Action::AllIn(x) => format!("Allin {}", bb(x)), _ => format!("{a:?}"),
    }
}

/// Every decision node of the starting street, plus the turn after unraised flop lines (check-check, bet-call) when
/// starting on the flop. Trimmed for size: hands with reach < 0.001 dropped, strategy as whole %, EV to 0.01 bb.
pub fn dump(g: &mut PostFlopGame) -> Map<String, Value> {
    g.back_to_root(); g.cache_normalized_weights();
    let mut out = Map::new();
    walk(g, &mut vec![], &mut vec![], 0, false, &mut out);
    out
}

fn walk(g: &mut PostFlopGame, hist: &mut Vec<usize>, key: &mut Vec<String>, street: u8, raised: bool, out: &mut Map<String, Value>) {
    if g.is_terminal_node() { return; }
    if g.is_chance_node() {
        if street > 0 || raised || g.current_board().len() > 3 { return; }
        let cards = g.possible_cards();
        for c in (0..52u8).filter(|c| cards >> c & 1 == 1) {
            g.play(c as usize); g.cache_normalized_weights(); hist.push(c as usize); key.push(card_to_string(c).unwrap());
            walk(g, hist, key, 1, false, out);
            hist.pop(); key.pop(); g.apply_history(hist); g.cache_normalized_weights();
        }
        return;
    }
    let p = g.current_player();
    let acts = g.available_actions();
    let n = g.private_cards(p).len();
    let (st, ev, reach) = (g.strategy(), g.expected_values_detail(p), g.normalized_weights(p).to_vec());
    let keep: Vec<usize> = (0..n).filter(|&h| reach[h] >= 0.001).collect();
    let hands = holes_to_strings(g.private_cards(p)).unwrap();
    let r = |x: f32, k: f64| ((x as f64) * k).round() / k;
    let per = |v: &[f32], k: f64, s: f64| (0..acts.len()).map(|a| keep.iter().map(|&h| r(v[a * n + h] * s as f32, k)).collect::<Vec<_>>()).collect::<Vec<_>>();
    out.insert(key.join("-"), json!({
        "player": p,
        "actions": acts.iter().map(act).collect::<Vec<_>>(),
        "hands": keep.iter().map(|&h| hands[h].clone()).collect::<Vec<_>>(),
        "reach": keep.iter().map(|&h| r(reach[h], 1000.0)).collect::<Vec<_>>(),
        "strat": per(&st, 1.0, 100.0),
        "ev": per(&ev, 100.0, 1.0 / CHIPS),
    }));
    for i in 0..acts.len() {
        let rz = matches!(acts[i], Action::Raise(_) | Action::AllIn(_));
        g.play(i); g.cache_normalized_weights(); hist.push(i); key.push(i.to_string());
        walk(g, hist, key, street, raised || (street == 0 && rz), out);
        hist.pop(); key.pop(); g.apply_history(hist); g.cache_normalized_weights();
    }
}

/// Browser entry: river(ptr, len) takes a job as UTF-8 JSON written into memory from alloc(len) and returns a pointer to
/// [u32 little-endian length][UTF-8 JSON]: {"iters", "exploit", "mem_mb", "nodes"} or {"error"}. free(ptr, 4 + length) the result (river frees the input).
#[cfg(target_arch = "wasm32")]
mod wasm {
    use super::*;

    fn leak(b: Box<[u8]>) -> *mut u8 { Box::leak(b).as_mut_ptr() }
    unsafe fn take(ptr: *mut u8, len: usize) -> Box<[u8]> { Box::from_raw(std::ptr::slice_from_raw_parts_mut(ptr, len)) }

    #[no_mangle]
    pub extern "C" fn alloc(len: usize) -> *mut u8 { leak(vec![0u8; len].into_boxed_slice()) }

    #[no_mangle]
    pub unsafe extern "C" fn free(ptr: *mut u8, len: usize) { drop(take(ptr, len)); }

    fn run(input: &str) -> Result<Value, String> {
        let j: Value = serde_json::from_str(input).map_err(|e| e.to_string())?;
        let mut g = game(&j)?;
        let mb = g.memory_usage().0 as f64 / 1048576.0;
        // a browser tab: refuse trees that would not fit comfortably (river subgames are normally tens of MB)
        let max_mb = j["max_mb"].as_f64().unwrap_or(1024.0);
        if mb > max_mb { return Err(format!("tree needs {mb:.0} MB > max_mb {max_mb}")); }
        g.allocate_memory(false);
        let (it, ex) = solve(&mut g, &j);
        Ok(json!({"iters": it, "exploit": ex, "mem_mb": mb.round(), "nodes": dump(&mut g)}))
    }

    #[no_mangle]
    pub unsafe extern "C" fn river(ptr: *mut u8, len: usize) -> *mut u8 {
        let input = String::from_utf8_lossy(&take(ptr, len)).into_owned();
        let out = run(&input).unwrap_or_else(|e| json!({"error": e})).to_string().into_bytes();
        let mut buf = (out.len() as u32).to_le_bytes().to_vec(); buf.extend(out);
        leak(buf.into_boxed_slice())
    }
}
