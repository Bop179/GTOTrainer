# python3 -I solver/make_jobs.py [outdir]   -> outdir/<scenario>/<flop>.json (default solver/jobs) + outdir/flops.json
# Heads-up single-raised pots at 6-max 100bb: ranges = the opener's raise weights and the caller's call weights from
# the trainer's preflop SPOTS rows ([allin, raise, call, fold, reach], percentages, 169 hands in grid order).
# ponytail: callers are assumed heads-up (players behind fold); squeeze/multiway lines are ignored.
import itertools, json, os, sys

R = "AKQJT98765432"
H = [R[i] + R[j] if i == j else (R[i] + R[j] + "s" if i < j else R[j] + R[i] + "o") for i in range(13) for j in range(13)]
SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data6.js")).read()
SCENARIOS = [("BTN", "BB"), ("CO", "BB"), ("SB", "BB"), ("HJ", "BB"), ("UTG", "BB"), ("CO", "BTN"), ("HJ", "BTN"), ("UTG", "BTN")]
SIZES = {"flop_sizes": ["33%, 75%", "2.5x"], "turn_sizes": ["75%", "2.5x"], "river_sizes": ["75%", "2.5x"]}
N_FLOPS = 95

def rows(key):
    i = SRC.index(json.dumps(key) + ":[[") + len(json.dumps(key)) + 1
    return json.JSONDecoder().raw_decode(SRC[i:])[0]

def rng(rs, col):
    return ",".join(f"{h}:{min(1, r[col] / 100 * r[4]):.3f}" for h, r in zip(H, rs) if r[col] * r[4] > 0.05)

def flops(n):
    """Representative flop subset: the 1755 suit-isomorphic flops, ordered by texture and weighted by how many
    real flops each stands for, sampled at n evenly spaced points of cumulative weight (so each pick ~ 1/n of deals)."""
    seen = {}
    for c in itertools.combinations([r + s for r in R for s in "shdc"], 3):
        # canonical form: the smallest spelling over all suit relabelings
        k = min("".join(sorted((x[0] + p["shdc".index(x[1])] for x in c), key=lambda x: (R.index(x[0]), x[1])))
                for p in itertools.permutations("shdc"))
        seen[k] = seen.get(k, 0) + 1
    tex = lambda k: (len(set(k[1::2])), len(set(k[0::2])), [R.index(x) for x in k[0::2]])
    keys = sorted(seen, key=tex)
    out, cum, step = [], 0, sum(seen.values()) / n
    for k in keys:
        cum += seen[k]
        while len(out) < n and cum >= step * (len(out) + 0.5): out.append(k)
    return out

def job(opener, caller, flop):
    o_size = json.loads(SRC.split(f'"6max/100bb/{opener}/RFI":', 2)[2].split("]", 1)[0] + "]")[0]  # SIZES entry
    pot = 2 * o_size + (0.5 if caller == "BB" else 1.5) - (0.5 if opener == "SB" else 0)
    o, c = rng(rows(f"6max/100bb/{opener}/RFI"), 1), rng(rows(f"6max/100bb/{opener}/{caller}/FACINGRFI"), 2)
    order = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]  # postflop action order: the later seat is in position
    ip_is_opener = order.index(opener) > order.index(caller)
    return {"oop": c if ip_is_opener else o, "ip": o if ip_is_opener else c, "flop": flop,
            "pot": pot, "stack": 100 - o_size, **SIZES, "target": 0.005, "max_iter": 1000}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs")
    fl = flops(N_FLOPS)
    assert len(fl) == N_FLOPS and len(set(fl)) == N_FLOPS
    assert job("SB", "BB", "AsKdQh")["oop"] == rng(rows("6max/100bb/SB/RFI"), 1)  # SB is out of position
    assert job("CO", "BTN", "AsKdQh")["ip"] == rng(rows("6max/100bb/CO/BTN/FACINGRFI"), 2)  # BTN caller is in position
    assert job("BTN", "BB", "AsKdQh")["pot"] == 5.5 and job("SB", "BB", "AsKdQh")["pot"] == 7.0
    os.makedirs(out, exist_ok=True)
    json.dump(fl, open(os.path.join(out, "flops.json"), "w"))
    for o, c in SCENARIOS:
        d = os.path.join(out, f"6max_100bb_{o}_v_{c}"); os.makedirs(d, exist_ok=True)
        for f in fl: json.dump(job(o, c, f), open(os.path.join(d, f + ".json"), "w"))
    print(f"{len(SCENARIOS)} scenarios x {len(fl)} flops -> {out}")
