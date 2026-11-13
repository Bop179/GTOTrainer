#!/usr/bin/env python3
"""Queue dashboard for the solver VM. Binds 127.0.0.1 only; view from the Mac with
   ssh -N -L 8080:localhost:8080 gto-vm   then open http://localhost:8080
Reads ~/jobs, ~/results and ~/results/queue.log (written by run_queue.sh) plus /proc."""
import calendar, html, os, re, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
JOBS, RES = HOME / "jobs", HOME / "results"
FAIL = re.compile(r"^(\S+) FAILED jobs/(\S+)\.json\s*(.*)")
OK = re.compile(r"^(\S+) ok jobs/([^/]+)/(\S+)\.json solved: (\d+) iterations, exploitability ([\d.]+)% of pot, (\d+)s")


def parse_log(lines):
    """-> {scenario: [secs, ...]}, [recent FAILED lines], [(unix ts, scenario, secs) per solve]"""
    secs, failed, events = {}, [], []
    for ln in lines:
        m = OK.match(ln)
        if m:
            secs.setdefault(m[2], []).append(int(m[6]))
            try:
                events.append((calendar.timegm(time.strptime(m[1], "%Y-%m-%dT%H:%M:%SZ")), m[2], int(m[6])))
            except ValueError:
                pass
        elif " FAILED " in ln:
            failed.append(ln.strip())
    return secs, failed[-5:], events


def fmt(s):
    s = int(s)
    return f"{s // 86400}d {s % 86400 // 3600}h" if s >= 86400 else f"{s // 3600}h {s % 3600 // 60}m"


def current_job():
    for p in Path("/proc").glob("[0-9]*"):
        try:
            args = (p / "cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if args[0].endswith(b"gto-solve") and len(args) > 1 and args[1].startswith(b"jobs/"):
            return args[1].decode(), time.time() - p.stat().st_ctime
    return None, 0


def sysinfo():
    """-> service state, loadavg, RAM used GB, RAM total GB; placeholders where /proc or systemctl is missing (a Mac preview)."""
    try:
        svc = subprocess.run(["systemctl", "is-active", "gto-queue"], capture_output=True, text=True).stdout.strip() or "unknown"
    except OSError:
        svc = "unknown"
    try:
        load = open("/proc/loadavg").read().split()[:3]
        mem = dict(l.split(":") for l in open("/proc/meminfo"))
        kb = lambda k: int(mem[k].split()[0])
        return svc, load, (kb("MemTotal") - kb("MemAvailable")) / 2**20, kb("MemTotal") / 2**20
    except OSError:
        return svc, ["–"] * 3, 0, 0


# ---- charts: inline SVG, one accent colour, hover text via <title> ----
CW, CH = 620, 300
X0, X1, Y0, Y1 = 38, CW - 10, 10, CH - 20
nice = lambda v: f"{v:.0f}" if v >= 10 else f"{v:.1f}"


def chart(title, body, ymax, xl="", xr="", note=""):
    return (f"<figure><figcaption>{title}</figcaption><svg viewBox='0 0 {CW} {CH}' role=img aria-label='{html.escape(title)}'>"
            f"<line class=ax x1={X0} x2={X1} y1={Y1} y2={Y1} /><line class=gr x1={X0} x2={X1} y1={Y0} y2={Y0} />"
            f"<text class=t x={X0 - 5} y={Y0 + 4} text-anchor=end>{ymax}</text><text class=t x={X0 - 5} y={Y1} text-anchor=end>0</text>"
            f"<text class=t x={X0} y={CH - 5}>{xl}</text><text class=t x={X1} y={CH - 5} text-anchor=end>{xr}</text>{body}</svg>"
            f"{f'<small>{note}</small>' if note else ''}</figure>")


def daily_bars(events, now, days=14):
    day = lambda t: int(t // 86400)
    counts = [0] * days
    for t, _, _ in events:
        i = day(t) - (day(now) - days + 1)
        if 0 <= i < days:
            counts[i] += 1
    top = max(counts) or 1
    bw = (X1 - X0) / days
    bars = "".join(
        f"<rect class=bar x={X0 + i * bw + 1:.1f} y={Y1 - (Y1 - Y0) * c / top:.1f} width={bw - 2:.1f} height={(Y1 - Y0) * c / top:.1f} rx=3>"
        f"<title>{time.strftime('%b %d', time.gmtime((day(now) - days + 1 + i) * 86400))}: {c} solves</title></rect>"
        for i, c in enumerate(counts) if c)
    return chart("Solves per day (UTC)", bars, top, time.strftime("%b %d", time.gmtime(now - (days - 1) * 86400)), "today"), counts


def solve_times(events, n=100):
    pts = [e[2] / 60 for e in events[-n:]]
    if len(pts) < 2:
        return chart("Solve time (minutes, last 100)", "", "–", note="waiting for data")
    top = max(pts) * 1.05
    xy = [(X0 + (X1 - X0) * i / (len(pts) - 1), Y1 - (Y1 - Y0) * p / top) for i, p in enumerate(pts)]
    line = "<polyline class=ln points='" + " ".join(f"{x:.1f},{y:.1f}" for x, y in xy) + "'/>"
    dots = "".join(f"<circle class=dot cx={x:.1f} cy={y:.1f} r=3><title>{e[1]}: {e[2] // 60}m {e[2] % 60}s</title></circle>"
                   for (x, y), e in zip(xy, events[-n:]))
    return chart("Solve time (minutes, last 100)", line + dots, nice(top), "older", "latest")


def progress_curve(events, now, done, total, eta):
    """Solves so far (solid) and the projection to the last solve at the current ETA (dashed)."""
    if len(events) < 2 or eta <= 0:
        return chart("Progress and projection", "", total, note="waiting for data")
    t0, t1 = events[0][0], now + eta
    sx = lambda t: X0 + (X1 - X0) * (t - t0) / (t1 - t0)
    sy = lambda v: Y1 - (Y1 - Y0) * v / total
    base = done - len(events)  # solves finished before the log began
    pts = [(sx(t), sy(base + i + 1)) for i, (t, _, _) in enumerate(events)]
    now_pt = pts[-1]
    solid = "<polyline class=ln points='" + " ".join(f"{x:.1f},{y:.1f}" for x, y in [(sx(t0), sy(base))] + pts) + "'/>"
    dash = f"<line class='ln proj' x1={now_pt[0]:.1f} y1={now_pt[1]:.1f} x2={X1} y2={Y0}><title>projected finish {time.strftime('%b %d', time.gmtime(t1))}</title></line>"
    return chart("Progress and projection (solves)", solid + dash + f"<circle class=dot cx={now_pt[0]:.1f} cy={now_pt[1]:.1f} r=4 />",
                 total, time.strftime("%b %d", time.gmtime(t0)), time.strftime("%b %d", time.gmtime(t1)), "dashed = at the current per-scenario averages")


def page():
    try:
        log = (RES / "queue.log").read_text().splitlines()
    except FileNotFoundError:
        log = []
    now = time.time()
    secs, failed, events = parse_log(log)
    allsecs = [s for v in secs.values() for s in v]
    overall = sum(allsecs[-20:]) / len(allsecs[-20:]) if allsecs else 0
    rows, eta, tot_done, tot_all, tot_fail = [], 0, 0, 0, 0
    for sc in sorted(d.name for d in JOBS.iterdir() if d.is_dir()):
        total = len(list((JOBS / sc).glob("*.json")))
        done = len(list((RES / sc).glob("*.json.gz"))) if (RES / sc).is_dir() else 0
        nfail = len(list((RES / sc).glob("*.failed"))) if (RES / sc).is_dir() else 0
        avg = sum(secs[sc]) / len(secs[sc]) if secs.get(sc) else overall
        left = total - done - nfail
        eta += left * avg
        tot_done, tot_all, tot_fail = tot_done + done, tot_all + total, tot_fail + nfail
        pct = 100 * done / total if total else 0
        rows.append(f"<tr><td>{html.escape(sc)}</td><td>{done}/{total}</td><td><div class=track><i style='width:{pct:.1f}%'></i></div></td>"
                    f"<td>{nfail or ''}</td><td>{fmt(avg) if avg else '–'}</td><td>{fmt(left * avg) if avg and left else '–'}</td></tr>")
    job, elapsed = current_job()
    svc, load, used, total_mem = sysinfo()
    svc_color = "var(--ok)" if svc == "active" else "var(--bad)"
    def fail_row(f):
        m = FAIL.match(f)
        return (f"<li><time>{html.escape(m[1][5:16].replace('T', ' '))}</time><b>{html.escape(m[2])}</b><span>{html.escape(m[3])}</span></li>"
                if m else f"<li><span>{html.escape(f)}</span></li>")
    fails = (f"<section class=fails><h3>Recent failures <em>{len(failed)}</em></h3><ul>{''.join(map(fail_row, failed))}</ul></section>" if failed
             else "<section class=fails><h3>Recent failures <em class=zero>none</em></h3></section>")
    pct = 100 * tot_done / tot_all if tot_all else 0
    fpct = 100 * tot_fail / tot_all if tot_all else 0
    day_chart, counts = daily_bars(events, now)
    last24 = sum(1 for e in events if e[0] > now - 86400)
    finish = time.strftime("%a %b %d, %H:%M UTC", time.gmtime(now + eta)) if eta else "–"
    tiles = "".join(f"<div class=tile><span>{k}</span><b>{v}</b></div>" for k, v in [
        ("ETA", fmt(eta) if eta else "–"), ("Finishes", finish), ("Last 24 h", f"{last24} solves"),
        ("Avg (last 20)", fmt(overall) if overall else "–"), ("Failed", tot_fail)])
    return f"""<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=30>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Solver queue</title>
<style>:root{{--bg:#fff;--fg:#111;--mut:#667;--grid:#8883;--ok:#2a9d6a;--bad:#d43}}
@media(prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#ddd;--mut:#99a;--ok:#4cc38a;--bad:#f66}}}}
body{{font:14px system-ui;margin:16px 0;padding:0 24px;background:var(--bg);color:var(--fg)}}
h2{{margin:0 0 8px}}.hero{{height:22px;background:var(--grid);border-radius:11px;overflow:hidden;display:flex}}
.hero i{{background:var(--ok)}}.hero u{{background:var(--bad)}}.sub{{color:var(--mut);margin:6px 0 14px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin-bottom:14px}}
.tile{{border:1px solid var(--grid);border-radius:8px;padding:8px 10px}}.tile span{{display:block;color:var(--mut);font-size:12px}}.tile b{{font-size:17px}}
.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:12px}}figure{{margin:0}}figcaption{{font-weight:600;margin-bottom:2px}}
svg{{width:100%;height:auto}}svg .t{{fill:var(--mut);font:13px system-ui}}svg .ax{{stroke:var(--mut)}}svg .gr{{stroke:var(--grid)}}
svg .bar{{fill:var(--ok)}}svg .ln{{fill:none;stroke:var(--ok);stroke-width:2}}svg .proj{{stroke-dasharray:5 4;opacity:.7}}
svg .dot{{fill:var(--ok);stroke:var(--bg);stroke-width:2}}figure small{{color:var(--mut)}}
.fails{{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 16px;border-left:3px solid var(--bad);padding:4px 12px;margin:0 0 14px;background:var(--grid);border-radius:0 6px 6px 0}}
.fails h3{{margin:0;font-size:13px}}.fails em{{font-style:normal;background:var(--bad);color:#fff;border-radius:9px;padding:0 7px;font-size:11px}}.fails em.zero{{background:none;color:var(--ok);padding:0}}
.fails ul{{list-style:none;margin:0;padding:0;flex:1 1 100%;display:grid;gap:2px}}.fails li{{display:flex;gap:10px;font:12px ui-monospace,monospace;white-space:nowrap;overflow:hidden}}
.fails li span{{color:var(--mut);overflow:hidden;text-overflow:ellipsis}}.fails time{{color:var(--mut)}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:4px 8px;text-align:left;border-bottom:1px solid var(--grid)}}
.track{{width:160px;height:10px;background:var(--grid);border-radius:5px;overflow:hidden}}.track i{{display:block;height:100%;background:var(--ok)}}code{{font-size:12px}}</style>
<h2>Solver queue: {tot_done}/{tot_all} flops ({pct:.1f}%)</h2>
<div class=hero role=progressbar aria-valuenow={pct:.1f} aria-valuemin=0 aria-valuemax=100 title="{pct:.1f}% done, {fpct:.1f}% failed"><i style="width:{pct:.2f}%"></i><u style="width:{fpct:.2f}%"></u></div>
<p class=sub>ETA {fmt(eta) if eta else '–'}, done {finish} · gto-queue <b style="color:{svc_color}">{html.escape(svc)}</b> · now <code>{html.escape(job or 'idle')}</code>{f' ({fmt(elapsed)} in)' if job else ''} ·
load {' '.join(load)} (4 cores) · RAM {used:.1f}/{total_mem:.1f} GB</p>
<div class=tiles>{tiles}</div>
{fails}
<div class=charts>{progress_curve(events, now, tot_done, tot_all, eta)}{day_chart}{solve_times(events)}</div>
<h3>Scenarios</h3>
<table><tr><th>Scenario</th><th>Done</th><th></th><th>Failed</th><th>Avg</th><th>ETA</th></tr>{''.join(rows)}</table>
<p class=sub><small>{time.strftime('%F %T UTC', time.gmtime(now))} · refreshes every 30 s</small></p>"""


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = page().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    if sys.argv[1:] == ["test"]:
        s, f, ev = parse_log(["2026-11-13T22:00:00Z ok jobs/6max_100bb_BTN_v_BB/5c5d2c.json solved: 1000 iterations, exploitability 0.290% of pot, 812s",
                              "2026-11-13T22:10:00Z FAILED jobs/6max_100bb_CO_v_BB/AhKd2c.json tree too big"])
        assert s == {"6max_100bb_BTN_v_BB": [812]} and len(f) == 1 and ev == [(1794607200, "6max_100bb_BTN_v_BB", 812)], (s, f, ev)
        assert fmt(90061) == "1d 1h" and fmt(3720) == "1h 2m"
        _, counts = daily_bars(ev, 1794607200 + 3600)
        assert counts[-1] == 1 and sum(counts) == 1, counts
        print("ok")
    else:
        ThreadingHTTPServer(("127.0.0.1", 8080), H).serve_forever()
