# python3 -I solver/make_jobs.py [outdir]   -> outdir/<scenario>/<flop>.json (default solver/jobs), outdir/order.txt
# (scenarios, most common first: the queue's order) and outdir/flops_<n>.json (each flop subset).
# Heads-up single-raised pots at 6-max 100bb, every opener/caller pair: ranges = the opener's raise weights and the caller's call weights from
# the trainer's preflop SPOTS rows ([allin, raise, call, fold, reach], percentages, 169 hands in grid order).
# ponytail: callers are assumed heads-up (players behind fold); squeeze/multiway lines are ignored.
import itertools, json, os, sys

R = "AKQJT98765432"
H = [R[i] + R[j] if i == j else (R[i] + R[j] + "s" if i < j else R[j] + R[i] + "o") for i in range(13) for j in range(13)]
SRC = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data6.js")).read()
SEATS = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]
SIZES = {"flop_sizes": ["33%, 75%", "2.5x"], "turn_sizes": ["75%, 125%", "2.5x"], "river_sizes": ["75%", "2.5x"]}
N_FLOPS, N_FLOPS_RARE = 95, 40
RARE = 0.05  # matchups under 5% of heads-up single-raised pots get the smaller flop set
COMBOS = [6 if h[0] == h[1] else 4 if h.endswith("s") else 12 for h in H]

def rows(key):
    i = SRC.index(json.dumps(key) + ":[[") + len(json.dumps(key)) + 1
    return json.JSONDecoder().raw_decode(SRC[i:])[0]

def rng(rs, col):
    return ",".join(f"{h}:{min(1, r[col] / 100 * r[4]):.3f}" for h, r in zip(H, rs) if r[col] * r[4] > 0.05)

def freq(rs, col):
    """Share of all 1326 combos taking action col (rows are per hand class, in percent, times reach)."""
    return sum(c * r[col] / 100 * r[4] for c, r in zip(COMBOS, rs)) / 1326

def scenarios():
    """Every opener/caller pair with data, most common first, as (share of heads-up single-raised pots, opener, caller).
    ponytail: share = open freq x flat freq, ignoring the players behind; good enough to rank and split common/rare."""
    out = [(freq(rows(f"6max/100bb/{o}/RFI"), 1) * freq(rows(f"6max/100bb/{o}/{c}/FACINGRFI"), 2), o, c)
           for i, o in enumerate(SEATS[:-1]) for c in SEATS[i + 1:] if f'"6max/100bb/{o}/{c}/FACINGRFI"' in SRC]
    tot = sum(f for f, _, _ in out)
    return sorted(((f / tot, o, c) for f, o, c in out), reverse=True)

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
    dead = (0 if "SB" in (opener, caller) else 0.5) + (0 if caller == "BB" else 1)  # blinds not in the pot's two players
    pot = 2 * o_size + dead
    o, c = rng(rows(f"6max/100bb/{opener}/RFI"), 1), rng(rows(f"6max/100bb/{opener}/{caller}/FACINGRFI"), 2)
    order = ["SB", "BB", "UTG", "HJ", "CO", "BTN"]  # postflop action order: the later seat is in position
    ip_is_opener = order.index(opener) > order.index(caller)
    return {"oop": c if ip_is_opener else o, "ip": o if ip_is_opener else c, "flop": flop,
            "pot": pot, "stack": 100 - o_size, **SIZES, "target": 0.01, "max_iter": 1000}

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs")
    sets = {n: flops(n) for n in (N_FLOPS, N_FLOPS_RARE)}
    assert all(len(f) == n and len(set(f)) == n for n, f in sets.items())
    assert job("SB", "BB", "AsKdQh")["oop"] == rng(rows("6max/100bb/SB/RFI"), 1)  # SB is out of position
    assert job("CO", "BTN", "AsKdQh")["ip"] == rng(rows("6max/100bb/CO/BTN/FACINGRFI"), 2)  # BTN caller is in position
    assert [job(o, c, "AsKdQh")["pot"] for o, c in [("BTN", "BB"), ("SB", "BB"), ("CO", "BTN"), ("BTN", "SB")]] == [5.5, 7.0, 6.5, 6.0]
    os.makedirs(out, exist_ok=True)
    for n, f in sets.items(): json.dump(f, open(os.path.join(out, f"flops_{n}.json"), "w"))
    order = []
    for share, o, c in scenarios():
        name, fl = f"6max_100bb_{o}_v_{c}", sets[N_FLOPS if share >= RARE else N_FLOPS_RARE]
        d = os.path.join(out, name); os.makedirs(d, exist_ok=True)
        for f in fl: json.dump(job(o, c, f), open(os.path.join(d, f + ".json"), "w"))
        order.append(name); print(f"{name:<22} {share:6.1%}  {len(fl)} flops")
    open(os.path.join(out, "order.txt"), "w").write("\n".join(order) + "\n")
    print(f"{len(order)} scenarios, {sum(len(os.listdir(os.path.join(out, d))) for d in order)} jobs -> {out}")
