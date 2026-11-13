// gto-solve: solve one heads-up postflop spot and dump its decision nodes (format in lib.rs). Runs on the VM only.
// Usage: gto-solve job.json out.json
// out: {"flop","pot","stack","exploit","iters","secs","mem_gb","nodes"}
use gto_solve::*;
use serde_json::{json, Value};
use std::time::Instant;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let j: Value = serde_json::from_str(&std::fs::read_to_string(&args[1]).unwrap()).unwrap();
    let mut g = game(&j).unwrap();
    let mem = g.memory_usage();
    let gb = |x: u64| x as f64 / 1073741824.0;
    // 16-bit storage halves memory (negligible accuracy cost); forced above 16 GB so the 23 GB VM never runs out
    let compress = j["compress"].as_bool().unwrap_or(false) || gb(mem.0) > 16.0;
    let mem_gb = gb(if compress { mem.1 } else { mem.0 });
    eprintln!("memory {:.2} GB (compressed {:.2} GB)", gb(mem.0), gb(mem.1));
    // refuse to allocate past the machine's budget (job "max_gb", default 20 for the 24 GB VM) instead of swapping
    let max_gb = j["max_gb"].as_f64().unwrap_or(20.0);
    if mem_gb > max_gb { eprintln!("needs {mem_gb:.1} GB > max_gb {max_gb}: use fewer bet sizes or \"compress\": true"); std::process::exit(2); }
    g.allocate_memory(compress);
    let t = Instant::now();
    let (it, ex) = solve(&mut g, &j);
    let secs = t.elapsed().as_secs_f64();
    eprintln!("solved: {it} iterations, exploitability {:.3}% of pot, {secs:.0}s", ex * 100.0);
    let nodes = dump(&mut g);
    let n = nodes.len();
    let out = json!({"flop": j["flop"], "pot": j["pot"], "stack": j["stack"], "iters": it, "secs": secs.round(),
        "mem_gb": (mem_gb * 100.0).round() / 100.0, "exploit": ex, "nodes": nodes});
    std::fs::write(&args[2], out.to_string()).unwrap();
    eprintln!("{n} flop+turn nodes -> {}", args[2]);
}
