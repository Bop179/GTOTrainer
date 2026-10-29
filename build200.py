#!/usr/bin/env python3
"""Read RangeConverter's free 6-max 200bb chart PDF into data200.js (extra spots for index.html).
The charts are images, so each cell is read by colour: fill height = how often the hand reaches
the spot, stripe widths = the action mix. Run: python3 build200.py [path/to/pdf]"""
import io, json, pathlib, re, sys, urllib.request
import numpy as np, pypdf

URL = "https://rangeconverter.com/downloads/6-max-200bb-Poker-Charts-No-Limit-Texas-Holdem-Cash"
HANDS = json.loads(re.search(r"window\.HANDS=(\[.*?\]);", pathlib.Path(__file__).with_name("data.js").read_text())[1])
ORDER = ["UTG", "HJ", "CO", "BTN", "SB", "BB"]  # the PDF calls HJ "MP"
COLORS = {"Raise": (227, 130, 20), "Call": (64, 145, 108), "Fold": (39, 125, 161),
          "empty": (45, 58, 68), "none": (18, 38, 60),  # empty = unfilled part of a cell, none = hand not in range
          "bg": (15, 27, 50), "border": (7, 24, 53)}  # page background: not part of any cell
# self-check. Cells read by eye off the charts: [allin, raise, call, fold, reach]
CELLS = {("6max/200bb/BB/UTG/FACING3B", "AA"): [0, 100, 0, 0, 1], ("6max/200bb/BB/UTG/FACING3B", "KK"): [0, 0, 100, 0, 1],
         ("6max/200bb/BB/UTG/FACING3B", "AKs"): [0, 50, 50, 0, 1], ("6max/200bb/BB/UTG/FACING3B", "JTo"): [0, 0, 0, 100, 0],
         ("6max/200bb/SB/RFI", "A6s"): [0, 50, 50, 0, 1], ("6max/200bb/UTG/RFI", "A2s"): [0, 0, 0, 100, 1],
         ("6max/200bb/BTN/SB/FACINGRFI", "66"): [0, 100, 0, 0, 1]}
# Legend totals printed under the charts. The drawings round each hand's mix to 0/50/100%,
# so totals read back from them drift a few points from these.
LEGEND = {"6max/200bb/UTG/RFI": (0, 18.05, 0, 81.95), "6max/200bb/SB/RFI": (0, 39.16, 7.19, 53.65),
          "6max/200bb/UTG/SB/FACINGRFI": (0, 6.01, 0, 93.99), "6max/200bb/HJ/UTG/FACING3B": (0, 18.69, 23.23, 58.08),
          "6max/200bb/BB/UTG/FACING3B": (0, 9.11, 41.8, 49.08)}


def classify(img):
    """Per pixel: index into COLORS, or -1 for text/background/anti-aliasing."""
    d = np.stack([((img - c) ** 2).sum(-1) for c in COLORS.values()])
    k = d.argmin(0)
    return np.where((d.min(0) < 300) & (k < 5), k, -1)


def runs(mask, min_len, gap=8):
    """(start, end) of runs of True at least min_len long, bridging the thin gaps between cells."""
    idx = np.flatnonzero(mask)
    if not len(idx):
        return []
    cut = np.flatnonzero(np.diff(idx) > gap)
    return [(a, b) for a, b in zip(np.r_[idx[0], idx[cut + 1]], np.r_[idx[cut], idx[-1]] + 1) if b - a >= min_len]


def read_page(img):
    """Every 13x13 chart on the page, in reading order, as rows of [allin, raise, call, fold, reach]."""
    cls = classify(img.astype(int))
    H, W = cls.shape
    charts = []
    for sy, sx in [(sy, sx) for sy in range(2) for sx in range(4)]:  # pages lay out up to 4x2 charts
        slot = cls[sy * H // 2:(sy + 1) * H // 2, sx * W // 4:(sx + 1) * W // 4] >= 0
        ys = runs(slot.mean(1) > 0.3, 400)  # the grid; the legend bars below it are too short
        if not ys:
            continue  # empty slot
        (y0, y1), = ys
        (x0, x1), = runs(slot[y0:y1].mean(0) > 0.5, 400)
        y0, y1, x0, x1 = y0 + sy * H // 2, y1 + sy * H // 2, x0 + sx * W // 4, x1 + sx * W // 4
        cw, ch = (x1 - x0) / 13, (y1 - y0) / 13
        grid = {}
        for r in range(13):
            for c in range(13):
                cell = cls[int(y0 + r * ch) + 3:int(y0 + (r + 1) * ch) - 3, int(x0 + c * cw) + 3:int(x0 + (c + 1) * cw) - 3]
                act, blank = (cell >= 0) & (cell <= 2), (cell == 3) | (cell == 4)
                filled = act.sum(1) > blank.sum(1)  # per pixel row: action colour or empty?
                known = filled | (blank.sum(1) > act.sum(1))
                reach = filled.sum() / max(known.sum(), 1)
                # per pixel column of the filled part: which action stripe it belongs to
                votes = np.stack([(cell[filled] == k).sum(0) for k in range(3)])
                cols = votes[:, votes.sum(0) > 0].argmax(0)
                mix = [100 * (cols == k).mean() if reach else 0 for k in range(3)]  # raise, call, fold
                grid[r, c] = [0, *mix, round(reach, 2)] if reach else [0, 0, 0, 100, 0]
        charts.append(grid)
    return charts


def hand_at(r, c):
    R = "AKQJT98765432"
    return R[r] * 2 if r == c else R[r] + R[c] + "s" if r < c else R[c] + R[r] + "o"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else None
    data = pathlib.Path(src).read_bytes() if src else urllib.request.urlopen(
        urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})).read()
    spots = {}
    for page in pypdf.PdfReader(io.BytesIO(data)).pages:
        title = " ".join((page.extract_text() or "").split()).replace("MP", "HJ")
        if title.startswith("Raise First In"):
            keys = [f"6max/200bb/{p}/RFI" for p in ORDER[:-1]]
        elif m := re.match(r"\s*(\w+) vs RFI", title):
            hero = m[1]
            keys = [f"6max/200bb/{v}/{hero}/FACINGRFI" for v in ORDER[:ORDER.index(hero)]]
        elif m := re.match(r"\s*(\w+) RFI vs 3bet", title):
            hero = m[1]
            keys = [f"6max/200bb/{v}/{hero}/FACING3B" for v in ORDER[ORDER.index(hero) + 1:]]
        else:
            continue  # cover and how-to pages
        charts = read_page(np.asarray(page.images[0].image.convert("RGB")))
        assert len(charts) == len(keys), f"{title[:40]!r}: found {len(charts)} charts, expected {len(keys)}"
        for key, grid in zip(keys, charts):
            rows = {hand_at(r, c): v for (r, c), v in grid.items()}
            # mixes snap to 10% to drop pixel noise (the charts only draw 50% steps)
            spots[key] = [[int(round(x, -1)) for x in rows[h][:4]] + [rows[h][4]] for h in HANDS]

    for (key, h), want in CELLS.items():
        got = spots[key][HANDS.index(h)]
        assert all(abs(g - x) < 0.1 * (100 if i < 4 else 1) for i, (g, x) in enumerate(zip(got, want))), f"{key} {h}: got {got}, chart shows {want}"
    combos = lambda h: 6 if len(h) == 2 else 4 if h[2] == "s" else 12
    for key, want in LEGEND.items():
        w = [combos(h) * row[4] for h, row in zip(HANDS, spots[key])]
        got = [sum(wi * row[i] for wi, row in zip(w, spots[key])) / sum(w) for i in range(4)]
        assert all(abs(g - x) < 6 for g, x in zip(got, want)), f"{key}: got {[round(g, 1) for g in got]}, chart says {want}"

    out = pathlib.Path(__file__).with_name("data200.js")
    out.write_text("Object.assign(window.SPOTS," + json.dumps(spots, separators=(",", ":")) + ");\n")
    print(f"{len(spots)} spots -> {out} ({out.stat().st_size // 1024} KB), self-check passed")


if __name__ == "__main__":
    main()
