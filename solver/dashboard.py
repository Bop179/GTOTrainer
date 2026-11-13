#!/usr/bin/env python3
"""Queue dashboard for the solver VM. Binds 127.0.0.1 only; view from the Mac with
   ssh -N -L 8080:localhost:8080 gto-vm   then open http://localhost:8080
Reads ~/jobs, ~/results and ~/results/queue.log (written by run_queue.sh) plus /proc."""
import html, os, re, subprocess, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOME = Path.home()
JOBS, RES = HOME / "jobs", HOME / "results"
OK = re.compile(r"^(\S+) ok jobs/([^/]+)/(\S+)\.json solved: (\d+) iterations, exploitability ([\d.]+)% of pot, (\d+)s")


def parse_log(lines):
    """-> {scenario: [secs, ...]}, [recent FAILED lines]"""
    secs, failed = {}, []
    for ln in lines:
        m = OK.match(ln)
        if m:
            secs.setdefault(m[2], []).append(int(m[6]))
        elif " FAILED " in ln:
            failed.append(ln.strip())
    return secs, failed[-5:]


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


def page():
    try:
        log = (RES / "queue.log").read_text().splitlines()
    except FileNotFoundError:
        log = []
    secs, failed = parse_log(log)
    allsecs = [s for v in secs.values() for s in v]
    overall = sum(allsecs[-20:]) / len(allsecs[-20:]) if allsecs else 0
    rows, eta, tot_done, tot_all = [], 0, 0, 0
    for sc in sorted(d.name for d in JOBS.iterdir() if d.is_dir()):
        total = len(list((JOBS / sc).glob("*.json")))
        done = len(list((RES / sc).glob("*.json.gz"))) if (RES / sc).is_dir() else 0
        nfail = len(list((RES / sc).glob("*.failed"))) if (RES / sc).is_dir() else 0
        avg = sum(secs[sc]) / len(secs[sc]) if secs.get(sc) else overall
        left = total - done - nfail
        eta += left * avg
        tot_done, tot_all = tot_done + done, tot_all + total
        pct = 100 * done / total if total else 0
        rows.append(f"<tr><td>{html.escape(sc)}</td><td>{done}/{total}</td><td><div class=bar><i style='width:{pct:.1f}%'></i></div></td>"
                    f"<td>{nfail or ''}</td><td>{fmt(avg) if avg else '–'}</td><td>{fmt(left * avg) if avg and left else '–'}</td></tr>")
    job, elapsed = current_job()
    svc = subprocess.run(["systemctl", "is-active", "gto-queue"], capture_output=True, text=True).stdout.strip() or "unknown"
    svc_color = "#3a7" if svc == "active" else "#d43"
    load = open("/proc/loadavg").read().split()[:3]
    mem = dict(l.split(":") for l in open("/proc/meminfo"))
    kb = lambda k: int(mem[k].split()[0])
    used, total_mem = (kb("MemTotal") - kb("MemAvailable")) / 2**20, kb("MemTotal") / 2**20
    fails = "".join(f"<li><code>{html.escape(f)}</code></li>" for f in failed) or "<li>none</li>"
    return f"""<!doctype html><meta charset=utf-8><meta http-equiv=refresh content=30>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Solver queue</title>
<style>body{{font:14px system-ui;margin:16px;max-width:900px;background:#fff;color:#111}}
@media(prefers-color-scheme:dark){{body{{background:#111;color:#ddd}}}}
table{{border-collapse:collapse;width:100%}}td,th{{padding:4px 8px;text-align:left;border-bottom:1px solid #8884}}
.bar{{width:160px;height:10px;background:#8883}}.bar i{{display:block;height:100%;background:#3a7}}code{{font-size:12px}}</style>
<h2>Solver queue — {tot_done}/{tot_all} flops, ETA {fmt(eta) if eta else '–'}</h2>
<p>Service gto-queue: <b style="color:{svc_color}">{html.escape(svc)}</b> · Now: <code>{html.escape(job or 'idle')}</code>{f' ({fmt(elapsed)} in)' if job else ''} ·
load {' '.join(load)} (4 cores) · RAM {used:.1f}/{total_mem:.1f} GB · avg last 20: {fmt(overall) if overall else '–'}</p>
<table><tr><th>Scenario</th><th>Done</th><th></th><th>Failed</th><th>Avg</th><th>ETA</th></tr>{''.join(rows)}</table>
<h3>Recent failures</h3><ul>{fails}</ul><p><small>{time.strftime('%F %T UTC', time.gmtime())} · refreshes every 30 s</small></p>"""


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
        s, f = parse_log(["2026-11-13T22:00:00Z ok jobs/6max_100bb_BTN_v_BB/5c5d2c.json solved: 1000 iterations, exploitability 0.290% of pot, 812s",
                          "2026-11-13T22:10:00Z FAILED jobs/6max_100bb_CO_v_BB/AhKd2c.json tree too big"])
        assert s == {"6max_100bb_BTN_v_BB": [812]} and len(f) == 1, (s, f)
        assert fmt(90061) == "1d 1h" and fmt(3720) == "1h 2m"
        print("ok")
    else:
        ThreadingHTTPServer(("127.0.0.1", 8080), H).serve_forever()
