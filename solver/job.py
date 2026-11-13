# python3 -I solver/job.py <data file> <opener RFI key> <caller FACINGRFI key> <flop> <pot> <stack> > job.json
# Builds a single-raised-pot job: IP/OOP ranges = the opener's raise weights and the caller's call weights
# from the trainer's preflop SPOTS rows ([allin, raise, call, fold, reach], percentages, 169 hands in grid order).
import json, re, sys

R = "AKQJT98765432"
H = [R[i] + R[j] if i == j else (R[i] + R[j] + "s" if i < j else R[j] + R[i] + "o") for i in range(13) for j in range(13)]

def rows(src, key):
    i = src.index(json.dumps(key) + ":[[") + len(json.dumps(key)) + 1
    return json.JSONDecoder().raw_decode(src[i:])[0]

def rng(rs, col):
    return ",".join(f"{h}:{min(1, r[col] / 100 * r[4]):.3f}" for h, r in zip(H, rs) if r[col] * r[4] > 0.05)

f, opener, caller, flop, pot, stack = sys.argv[1:7]
src = open(f).read()
o_seat, c_seat = opener.split("/")[-2], caller.split("/")[-2]
order = ["SB", "BB"]  # postflop the blinds act first; otherwise the later seat is IP
ip_is_opener = not (o_seat in order and (c_seat not in order or order.index(o_seat) < order.index(c_seat)))
o, c = rng(rows(src, opener), 1), rng(rows(src, caller), 2)
print(json.dumps({
    "oop": c if ip_is_opener else o, "ip": o if ip_is_opener else c,
    "flop": flop, "pot": float(pot), "stack": float(stack),
    "flop_sizes": ["33%, 75%", "2.5x"], "turn_sizes": ["50%, 100%", "2.5x"], "river_sizes": ["50%, 100%", "2.5x"],
    "target": 0.005, "max_iter": 1000,
}))
