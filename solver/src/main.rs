// gto-solve: solve one heads-up postflop spot with postflop-solver and dump the flop and (unraised-flop) turn decision nodes.
// Usage: gto-solve job.json out.json
// job: {"oop": range, "ip": range, "flop": "Td9d6h", "pot": 5.5, "stack": 97.5,      (pot/stack in bb)
//       "flop_sizes": ["33%, 75%", "2.5x"], "turn_sizes": [...], "river_sizes": [...],  ([bet, raise], both players)
//       "target": 0.005, "max_iter": 1000, "compress": false}
// out:  {"flop","pot","stack","exploit","iters","secs","mem_gb","nodes": {"<history, e.g. 0-1 or 0-1-Kh-0>": node}}
//       node = {"player": 0 OOP | 1 IP, "actions": ["Check","Bet 1.8",...], "hands": ["AhKh",...],
//               "reach": [normalized reach per hand], "strat": [[% per hand] per action], "ev": [[bb per hand] per action]}
use postflop_solver::*;
use serde_json::{json, Value};
use std::time::Instant;

const CHIPS: f64 = 20.0; // chips per bb (the solver works in integers)

fn sizes(j: &Value, k: &str) -> BetSizeOptions {
    let a = j[k].as_array().unwrap_or_else(|| panic!("{k} missing"));
    BetSizeOptions::try_from((a[0].as_str().unwrap(), a[1].as_str().unwrap())).unwrap()
}

fn act(a: &Action) -> String {
    let bb = |x: &i32| (*x as f64 / CHIPS * 100.0).round() / 100.0;
    match a {
        Action::Fold => "Fold".into(), Action::Check => "Check".into(), Action::Call => "Call".into(),
        Action::Bet(x) => format!("Bet {}", bb(x)), Action::Raise(x) => format!("Raise {}", bb(x)),
        Action::AllIn(x) => format!("Allin {}", bb(x)), _ => format!("{a:?}"),
    }
}

// Walk the flop, and the turn after every flop line without a raise (check-check, bet-call); stop at the river card.
// Key tokens: action indices and dealt cards, e.g. "0-1-Kh-0-2" = check, bet, call ... turn Kh, check, bet 2.
// Trimmed for size: hands with reach < 0.001 dropped, strategy as whole percentages, EV to 0.01 bb.
fn walk(g: &mut PostFlopGame, hist: &mut Vec<usize>, key: &mut Vec<String>, street: u8, raised: bool, out: &mut serde_json::Map<String, Value>) {
    if g.is_terminal_node() { return; }
    if g.is_chance_node() {
        if street > 0 || raised { return; }
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

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let j: Value = serde_json::from_str(&std::fs::read_to_string(&args[1]).unwrap()).unwrap();
    let f = |k: &str| j[k].as_f64().unwrap_or_else(|| panic!("{k} missing"));
    let card_config = CardConfig {
        range: [j["oop"].as_str().unwrap().parse().unwrap(), j["ip"].as_str().unwrap().parse().unwrap()],
        flop: flop_from_str(j["flop"].as_str().unwrap()).unwrap(),
        turn: NOT_DEALT, river: NOT_DEALT,
    };
    let (fl, tu, ri) = (sizes(&j, "flop_sizes"), sizes(&j, "turn_sizes"), sizes(&j, "river_sizes"));
    let tree = TreeConfig {
        initial_state: BoardState::Flop,
        starting_pot: (f("pot") * CHIPS).round() as i32,
        effective_stack: (f("stack") * CHIPS).round() as i32,
        rake_rate: 0.0, rake_cap: 0.0, // GTO Wizard preflop data is cEV, no rake
        flop_bet_sizes: [fl.clone(), fl], turn_bet_sizes: [tu.clone(), tu], river_bet_sizes: [ri.clone(), ri],
        turn_donk_sizes: None, river_donk_sizes: None,
        add_allin_threshold: 1.5, force_allin_threshold: 0.15, merging_threshold: 0.1,
    };
    let mut g = PostFlopGame::with_config(card_config, ActionTree::new(tree).unwrap()).unwrap();
    let compress = j["compress"].as_bool().unwrap_or(false);
    let mem = g.memory_usage();
    let mem_gb = (if compress { mem.1 } else { mem.0 }) as f64 / 1073741824.0;
    eprintln!("memory {:.2} GB (compressed {:.2} GB)", mem.0 as f64 / 1073741824.0, mem.1 as f64 / 1073741824.0);
    // refuse to allocate past the machine's budget (job "max_gb", default 20 for the 24 GB VM) instead of swapping
    let max_gb = j["max_gb"].as_f64().unwrap_or(20.0);
    if mem_gb > max_gb { eprintln!("needs {mem_gb:.1} GB > max_gb {max_gb}: use fewer bet sizes or \"compress\": true"); std::process::exit(2); }
    g.allocate_memory(compress);
    let t = Instant::now();
    let target = (f("pot") * CHIPS * j["target"].as_f64().unwrap_or(0.005)) as f32;
    let max_iter = j["max_iter"].as_u64().unwrap_or(1000) as u32;
    // solve in steps so the iteration count is known
    let mut it = 0; let mut ex = f32::MAX;
    while it < max_iter {
        solve_step(&g, it); it += 1;
        if it % 10 == 0 { ex = compute_exploitability(&g); if ex <= target { break; } }
    }
    finalize(&mut g);
    let secs = t.elapsed().as_secs_f64();
    eprintln!("solved: {it} iterations, exploitability {:.3}% of pot, {secs:.0}s", ex as f64 / (f("pot") * CHIPS) * 100.0);
    g.back_to_root(); g.cache_normalized_weights();
    let mut nodes = serde_json::Map::new();
    walk(&mut g, &mut vec![], &mut vec![], 0, false, &mut nodes);
    let out = json!({"flop": j["flop"], "pot": f("pot"), "stack": f("stack"), "iters": it, "secs": secs.round(), "mem_gb": (mem_gb * 100.0).round() / 100.0,
        "exploit": ex as f64 / (f("pot") * CHIPS), "nodes": nodes});
    std::fs::write(&args[2], serde_json::to_string(&out).unwrap()).unwrap();
    eprintln!("{} flop+turn nodes -> {}", out["nodes"].as_object().unwrap().len(), args[2]);
}
