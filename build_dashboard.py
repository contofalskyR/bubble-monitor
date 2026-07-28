"""
build_dashboard.py — renders docs/index.html + docs/thesis.html.

Design language: "midnight prospectus" (Fraunces serif numerals, champagne-gold
accent, deep midnight field). Beauty in service of analysis — post red-team,
symmetrically: cards warm toward confirm AND cool toward refute (F11), gauges
show distance to both rails, the stamp counts dark dials as loudly as alerts
(F5c), gap cards show the actual error (F12), and every status comes from the
same server.evaluate() the cron uses (F1).

Usage:
  python build_dashboard.py            # live FRED data (needs FRED_API_KEY)
  python build_dashboard.py --sample   # UI preview from the report's 25 Jul values
"""
from __future__ import annotations

import html
import json
import sys
from datetime import date
from pathlib import Path

from server import (FRED_KEY, fred_latest, spread_window, evaluate, assess_stage,
                    _load, TRIPWIRES_FILE, CALENDAR_FILE, JOURNAL_FILE)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "index.html"

# Report values as of 25 Jul 2026 — used only in --sample preview mode
SAMPLE_END = {"BAMLH0A0HYM2": 2.77, "BAMLH0A3HYC": 9.91, "BAMLC0A4CBBB": 0.98,
              "BAMLC0A0CM": 0.79, "DGS10": 4.71}


def esc(s) -> str:
    return html.escape(str(s))


def sample_series(series_id: str, n: int = 30) -> list[tuple[str, float]]:
    end = SAMPLE_END.get(series_id, 1.0)
    vals = [round(end * (0.94 + 0.06 * i / (n - 1)) + end * 0.006 * ((i * 7) % 5 - 2) / 2, 3)
            for i in range(n)]
    vals[-1] = end
    return [("", v) for v in vals]  # dates blank in preview


def spark_area(values: list[float], uid: str, tone: str,
               rails: tuple[float, float] | None = None) -> str:
    """Gradient area sparkline; draws dashed threshold rails when they fall
    inside the window's value range (F22)."""
    if len(values) < 2:
        return ""
    lo, hi = min(values), max(values)
    rng = (hi - lo) or 1.0
    y = lambda v: 30 - (v - lo) / rng * 22 + 2
    xy = [((i / (len(values) - 1) * 120), y(v)) for i, v in enumerate(values)]
    pts = " ".join(f"{x:.1f},{py:.1f}" for x, py in xy)
    lx, ly = xy[-1]
    rail_lines = ""
    if rails:
        r_lt, c_gt = rails
        for val, col in ((r_lt, "#7cb3ff"), (c_gt, "#f4694b")):
            if lo <= val <= hi:
                ry = y(val)
                rail_lines += (f'<line x1="0" y1="{ry:.1f}" x2="120" y2="{ry:.1f}" '
                               f'stroke="{col}" stroke-opacity=".45" stroke-width=".8" '
                               f'stroke-dasharray="3 3"/>')
    return (
        f'<svg viewBox="0 0 120 34" preserveAspectRatio="none" aria-hidden="true">'
        f'<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{tone}" stop-opacity=".28"/>'
        f'<stop offset="1" stop-color="{tone}" stop-opacity="0"/></linearGradient></defs>'
        f'{rail_lines}'
        f'<path d="M {pts} L 120,34 L 0,34 Z" fill="url(#g{uid})"/>'
        f'<polyline points="{pts}" fill="none" stroke="{tone}" stroke-opacity=".9" '
        f'stroke-width="1.4" vector-effect="non-scaling-stroke"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.4" fill="{tone}"/></svg>')


def gauge(cur: float, r_lt: float, c_gt: float) -> str:
    span = c_gt - r_lt
    pos = max(0.0, min(1.0, (cur - r_lt) / span)) * 100 if span else 50.0
    dc, dr = c_gt - cur, cur - r_lt
    return (
        f'<div class="gauge"><div class="gtrack"><div class="gdot" style="left:{pos:.1f}%"></div></div>'
        f'<div class="gmeta"><span class="gr">refute {r_lt:g} · Δ{dr:+g}</span>'
        f'<span class="gc">Δ{dc:+g} · confirm {c_gt:g}</span></div></div>')


def gather_dials(sample: bool):
    """Statuses come from server.evaluate() — the SAME function the cron uses,
    including session windows (F1/F2). Gaps carry their real error (F12)."""
    tw = _load(TRIPWIRES_FILE)["tripwires"]
    dials, alerts = [], []
    for t in tw:
        chk = t.get("check", {})
        kind = chk.get("type")
        if kind not in ("fred", "fred_spread"):
            continue
        sess = max(chk.get("sessions", 1), 1)
        try:
            if sample:
                if kind == "fred":
                    hist = sample_series(chk["series"])
                else:
                    a = sample_series(chk["series_a"]); b = sample_series(chk["series_b"])
                    hist = [("", round(x[1] - y[1], 2)) for x, y in zip(a, b)]
                tag, asof = "R", "report 25 Jul 26"
            else:
                need = max(30, sess)
                if kind == "fred":
                    obs = fred_latest(chk["series"], need + 10)
                else:
                    obs = spread_window(chk["series_a"], chk["series_b"], need)
                if len(obs) < sess:
                    raise RuntimeError(f"only {len(obs)}/{sess} sessions available")
                hist = list(reversed(obs[:need]))  # oldest-first for the sparkline
                tag, asof = "V", f"FRED {obs[0][0]}"
            vals = [v for _, v in hist]
            cur = vals[-1]
            status, prox = evaluate(chk, list(reversed(vals)))
            if status != "quiet" and not sample:
                alerts.append(f"{t['name']} at {cur} — {status} threshold crossed"
                              + (f" (all of last {sess} sessions)" if sess > 1 else ""))
            dials.append({"id": t["id"], "name": t["name"], "cur": cur, "vals": vals,
                          "delta": round(cur - vals[0], 2), "prox": prox,
                          "c_gt": chk["confirm_gt"], "r_lt": chk["refute_lt"],
                          "status": status.lower(), "sessions": sess,
                          "tag": tag, "asof": asof})
        except Exception as exc:
            dials.append({"id": t["id"], "name": t["name"], "gap": str(exc)})
    return dials, alerts


CSS = """
:root{--bg:#0a0d14;--panel:rgba(255,255,255,.032);--line:rgba(255,255,255,.085);
--text:#ece7dc;--mut:#96a0b5;--gold:#e3c47f;--confirm:#f4694b;--refute:#7cb3ff;--quiet:#9db894}
*{box-sizing:border-box;margin:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);
font:15.5px/1.5 "Spline Sans Mono",ui-monospace,"SF Mono",Menlo,monospace;
padding:26px 18px 56px;max-width:700px;margin:0 auto;font-variant-numeric:tabular-nums;
position:relative;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;
background:radial-gradient(90% 42% at 50% -6%,#18213a 0%,rgba(24,33,58,0) 68%)}
.bubbles{position:absolute;inset:0 0 auto 0;height:340px;overflow:hidden;pointer-events:none;z-index:-1}
.bubbles i{position:absolute;bottom:-24px;border-radius:50%;
border:1px solid rgba(227,196,127,.16);background:rgba(227,196,127,.03);
animation:rise linear infinite}
@keyframes rise{to{transform:translateY(-420px);opacity:0}}
.topnav{display:flex;gap:18px;justify-content:flex-end;font-size:10.5px;
text-transform:uppercase;letter-spacing:.18em;margin-bottom:18px}
.topnav a{color:var(--mut);text-decoration:none}.topnav a:hover{color:var(--gold)}
.topnav .on{color:var(--gold)}
.eyebrow{color:var(--gold);text-transform:uppercase;letter-spacing:.26em;font-size:10.5px;opacity:.85}
.masthead{font-family:"Fraunces","Iowan Old Style",Georgia,serif;font-weight:560;
font-size:34px;line-height:1.08;margin:8px 0 2px;letter-spacing:.1px}
.masthead em{font-style:italic;color:var(--gold);font-weight:480}
.rule{height:1px;background:linear-gradient(90deg,var(--gold),rgba(227,196,127,0));margin:14px 0 18px;opacity:.5}
.stamp{display:inline-block;position:relative;padding:8px 18px;border:1.5px solid var(--quiet);
color:var(--quiet);transform:rotate(-1.2deg);text-transform:uppercase;letter-spacing:.18em;
font-size:12.5px;border-radius:5px;background:rgba(157,184,148,.05)}
.stamp::after{content:"";position:absolute;inset:3px;border:1px solid currentColor;opacity:.35;border-radius:3px}
.stamp.hot{border-color:var(--confirm);color:var(--confirm);background:rgba(244,105,75,.06)}
.stamp.dark{border-color:var(--gold);color:var(--gold);background:rgba(227,196,127,.05)}
.stamp.gold{border-color:var(--gold);color:var(--gold);background:rgba(227,196,127,.05)}
.stampdate{color:var(--mut);font-size:11px;margin:8px 0 0}
.pulse{display:flex;gap:10px;margin:18px 0 4px;flex-wrap:wrap}
.pcell{flex:1;min-width:150px;background:var(--panel);border:1px solid var(--line);
border-radius:10px;padding:10px 12px}
.pk{font-size:9.5px;text-transform:uppercase;letter-spacing:.16em;color:var(--mut)}
.pv{font-size:13.5px;margin-top:3px}
.pv.hot{color:var(--confirm)}.pv.calm{color:var(--quiet)}.pv.gold{color:var(--gold)}.pv.cool{color:var(--refute)}
.alertline{color:var(--confirm);font-size:13px;margin:3px 0}
.preview{border:1px dashed var(--gold);color:var(--gold);font-size:12px;padding:9px 12px;
margin:16px 0;border-radius:8px;background:rgba(227,196,127,.04)}
h2{font-size:11px;text-transform:uppercase;letter-spacing:.22em;color:var(--mut);
margin:32px 0 12px;font-weight:500;display:flex;align-items:center;gap:10px}
h2::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--gold);opacity:.7}
h2::after{content:"";flex:1;height:1px;background:var(--line)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
padding:14px 14px 12px;backdrop-filter:blur(6px);transition:border-color .3s}
.card.warm{border-color:rgba(227,196,127,.4);box-shadow:0 0 30px -10px rgba(227,196,127,.35)}
.card.cool{border-color:rgba(124,179,255,.35);box-shadow:0 0 30px -12px rgba(124,179,255,.3)}
.card.confirm{border-color:rgba(244,105,75,.55);box-shadow:0 0 34px -8px rgba(244,105,75,.4)}
.card.refute{border-color:rgba(124,179,255,.5);box-shadow:0 0 34px -8px rgba(124,179,255,.35)}
.chead{display:flex;justify-content:space-between;align-items:baseline;gap:6px}
.cname{font-size:11px;color:var(--mut);letter-spacing:.04em}
.delta{font-size:10.5px;padding:2px 7px;border-radius:99px;border:1px solid var(--line)}
.delta.up{color:var(--confirm);border-color:rgba(244,105,75,.3)}
.delta.dn{color:var(--refute);border-color:rgba(124,179,255,.3)}
.val{font-family:"Fraunces",Georgia,serif;font-weight:560;font-size:33px;margin:4px 0 2px;letter-spacing:.3px}
.card.confirm .val{color:var(--confirm)}.card.refute .val{color:var(--refute)}
.spark{height:34px;margin:4px 0 6px}.spark svg{width:100%;height:34px;display:block}
.gauge{margin-top:2px}
.gtrack{position:relative;height:3px;border-radius:2px;
background:linear-gradient(90deg,rgba(124,179,255,.55),rgba(150,160,181,.25) 42%,rgba(227,196,127,.35) 72%,rgba(244,105,75,.6))}
.gdot{position:absolute;top:-3.5px;width:10px;height:10px;border-radius:50%;
background:var(--text);transform:translateX(-50%);box-shadow:0 0 10px rgba(236,231,220,.7)}
.gmeta{display:flex;justify-content:space-between;font-size:9.5px;margin-top:6px;letter-spacing:.03em}
.gr{color:var(--refute);opacity:.9}.gc{color:var(--confirm);opacity:.9}
.tag{font-size:10px;margin-top:9px;letter-spacing:.06em}
.tag.v{color:var(--quiet)}.tag.r,.tag.g{color:var(--gold)}
.gapnote{font-size:11px;color:var(--mut);margin-top:6px;line-height:1.5;word-break:break-word}
.gaperr{color:var(--gold)}
.timeline{position:relative;padding-left:22px}
.timeline::before{content:"";position:absolute;left:6px;top:6px;bottom:6px;width:1px;
background:linear-gradient(rgba(227,196,127,.5),var(--line) 30%,rgba(255,255,255,0))}
.ev{position:relative;display:flex;gap:12px;padding:11px 0;border-bottom:1px solid rgba(255,255,255,.05)}
.ev::before{content:"";position:absolute;left:-19.5px;top:17px;width:7px;height:7px;
border-radius:50%;background:var(--mut)}
.ev.lb::before{width:9px;height:9px;left:-20.5px;background:var(--gold);
box-shadow:0 0 12px rgba(227,196,127,.8)}
.chip{color:var(--gold);min-width:52px;font-size:13px;padding-top:1px}
.evname{font-size:14px;font-family:"Fraunces",Georgia,serif;font-weight:480;letter-spacing:.2px}
.ev.lb .evname{color:var(--gold)}
.evwatch{font-size:11.5px;color:var(--mut);margin-top:3px;line-height:1.45}
details{border:1px solid var(--line);border-radius:12px;margin-bottom:10px;
background:var(--panel);overflow:hidden}
summary{padding:12px 14px;cursor:pointer;text-transform:capitalize;font-size:13px;
display:flex;justify-content:space-between;list-style:none}
summary::-webkit-details-marker{display:none}
summary .n{color:var(--gold);font-size:11px}
.mt{padding:11px 14px;border-top:1px solid rgba(255,255,255,.05)}
.mtname{font-size:13.5px;font-family:"Fraunces",Georgia,serif;font-weight:480}
.mtnow{font-size:11.5px;color:var(--mut);margin:4px 0 6px;line-height:1.45}
.mtline{font-size:11.5px;margin:3px 0;line-height:1.45}
.statenote{font-size:11px;color:var(--gold);margin:3px 0 0;line-height:1.45;font-style:italic}
.k{display:inline-block;width:72px;text-transform:uppercase;letter-spacing:.1em;font-size:9px}
.k.c{color:var(--confirm)}.k.r{color:var(--refute)}
.jrow{display:flex;gap:12px;font-size:12.5px;padding:8px 2px;border-bottom:1px solid rgba(255,255,255,.05)}
.jkind{color:var(--gold);text-transform:uppercase;font-size:9.5px;min-width:64px;
letter-spacing:.12em;padding-top:3px}
.jrow.empty{color:var(--mut)}
footer{margin-top:40px;color:var(--mut);font-size:11px;line-height:1.7;
border-top:1px solid var(--line);padding-top:16px}
footer b{color:var(--gold);font-weight:500}
.stagewrap{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 16px}
.attrib{font-size:10.5px;color:var(--mut);margin-bottom:12px;line-height:1.55}
.assessbtn{font:inherit;font-size:12px;letter-spacing:.16em;text-transform:uppercase;
color:var(--gold);background:rgba(227,196,127,.07);border:1px solid rgba(227,196,127,.45);
border-radius:8px;padding:11px 20px;cursor:pointer;transition:all .25s}
.assessbtn:hover{background:rgba(227,196,127,.14);box-shadow:0 0 24px -8px rgba(227,196,127,.5)}
.assessbtn:disabled{opacity:.55;cursor:default;box-shadow:none}
#stagepanel{display:none;margin-top:16px}
#stagepanel.open{display:block}
.crit{display:flex;gap:10px;font-size:12px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.05);
opacity:0;transform:translateY(6px);transition:opacity .4s ease,transform .4s ease}
.open .crit{opacity:1;transform:none}
.crit .lvl{color:var(--mut);min-width:26px;font-size:10px;padding-top:2px}
.crit .mark{min-width:16px;color:var(--mut)}.crit.pass .mark{color:var(--gold)}
.crit.pass{color:var(--text)}.crit:not(.pass){color:var(--mut)}
.stageev{font-size:11.5px;color:var(--mut);margin-top:12px;line-height:1.7}
.stageev b{color:var(--gold);font-weight:500}
.overlay{border:1px solid rgba(124,179,255,.45);color:var(--refute);font-size:12px;
padding:9px 12px;border-radius:8px;margin-top:12px;background:rgba(124,179,255,.05)}
.warnband{border:1px solid rgba(227,196,127,.5);color:var(--gold);font-size:12px;
padding:9px 12px;border-radius:8px;margin-top:12px;background:rgba(227,196,127,.05)}
.pdfbtn{display:inline-block;font-size:12.5px;letter-spacing:.14em;text-transform:uppercase;
color:var(--bg);background:var(--gold);border-radius:8px;padding:13px 24px;text-decoration:none;
margin:18px 0;font-weight:500}
.thesisbody{font-size:14.5px;line-height:1.75;color:var(--text)}
.thesisbody p{margin:14px 0}.thesisbody .sec{color:var(--gold);font-size:10.5px;
text-transform:uppercase;letter-spacing:.2em;margin-top:26px}
@media (max-width:390px){.val{font-size:27px}.masthead{font-size:29px}}
@media (prefers-reduced-motion:reduce){
  html{scroll-behavior:auto}
  .bubbles i{animation:none;display:none}
  .crit{transition:none;opacity:1;transform:none}
  .assessbtn,.card{transition:none}
}
"""

BUBBLES = "".join(
    f'<i style="left:{x}%;width:{w}px;height:{w}px;animation-duration:{d}s;animation-delay:-{dl}s"></i>'
    for x, w, d, dl in [(8,7,26,3),(19,4,34,11),(31,9,22,7),(44,5,30,15),(58,6,27,1),
                        (69,4,36,19),(78,8,24,9),(90,5,31,5)])


def render(sample: bool) -> str:
    dials, alerts = gather_dials(sample)
    cal = _load(CALENDAR_FILE)["events"]
    manual = [t for t in _load(TRIPWIRES_FILE)["tripwires"] if t["check"]["type"] == "manual"]
    today = date.today()
    live = [d for d in dials if "gap" not in d]
    gap_dials = [d for d in dials if "gap" in d]

    cov = ""
    histf = ROOT / "data" / "history.csv"
    if histf.exists() and histf.stat().st_size > 0:
        runs = sorted({ln.split(",", 1)[0] for ln in histf.read_text().splitlines()[1:] if ln})
        if runs:
            cov = f" Monitoring since {runs[0]} · {len(runs)} daily checks on record."

    # journal tail — tolerant of a truncated line (F7)
    entries, bad_lines = [], 0
    if JOURNAL_FILE.exists():
        for ln in JOURNAL_FILE.read_text().strip().splitlines()[-6:]:
            try:
                entries.append(json.loads(ln))
            except json.JSONDecodeError:
                bad_lines += 1

    # stamp: darkness is as loud as alerts (F5c)
    n_dark = len(gap_dials)
    if alerts:
        stamp = f"{len(alerts)} tripwire{'s' if len(alerts) != 1 else ''} crossed"
        stamp += f" · {n_dark} dark" if n_dark else ""
        stamp_cls = "hot"
    elif n_dark:
        stamp = f"All quiet · {n_dark} dial{'s' if n_dark != 1 else ''} dark"
        stamp_cls = "dark"
    else:
        stamp, stamp_cls = "All quiet", ""

    # pulse strip — symmetric (F11): nearest threshold in EITHER direction
    next_lb = next((e for e in cal if e.get("load_bearing")
                    and date.fromisoformat(e["date"]) >= today), None)
    p1 = (f'<span class="pv hot">{len(alerts)} crossed</span>' if alerts
          else f'<span class="pv gold">{n_dark} dials dark</span>' if n_dark
          else '<span class="pv calm">nothing crossed</span>')
    quiet_live = [d for d in live if d["status"] == "quiet"]
    if quiet_live:
        nearest = min(quiet_live, key=lambda d: min(d["prox"], 1 - d["prox"]))
        if nearest["prox"] >= 0.5:
            p2 = (f'<span class="pv gold">{esc(nearest["name"])} · '
                  f'{nearest["c_gt"] - nearest["cur"]:g} below confirm</span>')
        else:
            p2 = (f'<span class="pv cool">{esc(nearest["name"])} · '
                  f'{nearest["cur"] - nearest["r_lt"]:g} above refute</span>')
    else:
        p2 = '<span class="pv">—</span>'
    if next_lb:
        dd = (date.fromisoformat(next_lb["date"]) - today).days
        nm = next_lb["event"]
        nm = nm[:30] + "…" if len(nm) > 31 else nm
        p3 = f'<span class="pv gold">{esc(nm)} · {dd}d</span>'
    else:
        p3 = '<span class="pv">—</span>'
    pulse = (f'<div class="pulse">'
             f'<div class="pcell"><div class="pk">Today</div>{p1}</div>'
             f'<div class="pcell"><div class="pk">Nearest threshold</div>{p2}</div>'
             f'<div class="pcell"><div class="pk">Next load-bearing date</div>{p3}</div></div>')

    # dial cards
    cards = []
    for i, d in enumerate(dials):
        if "gap" in d:
            cards.append(f'<div class="card"><div class="cname">{esc(d["name"])}</div>'
                         f'<div class="tag g">[G] no fetch</div>'
                         f'<div class="gapnote"><span class="gaperr">{esc(d["gap"])}</span><br>'
                         f'A dark dial is a finding, not a pass — if this persists, the series '
                         f'may have changed or been withdrawn.</div></div>')
            continue
        halo = (" warm" if d["status"] == "quiet" and d["prox"] >= 0.7
                else " cool" if d["status"] == "quiet" and d["prox"] <= 0.3 else "")
        dcls = "up" if d["delta"] > 0 else "dn" if d["delta"] < 0 else ""
        darrow = "▲" if d["delta"] > 0 else "▼" if d["delta"] < 0 else "·"
        tone = ("#f4694b" if d["status"] == "confirm" or d["prox"] >= 0.7
                else "#7cb3ff" if d["status"] == "refute" or d["prox"] <= 0.3
                else "#e3c47f")
        cards.append(
            f'<div class="card {d["status"]}{halo}">'
            f'<div class="chead"><div class="cname">{esc(d["name"])}</div>'
            f'<span class="delta {dcls}">{darrow} {d["delta"]:+g} · 30 sess</span></div>'
            f'<div class="val">{d["cur"]:g}</div>'
            f'<div class="spark">{spark_area(d["vals"], str(i), tone, (d["r_lt"], d["c_gt"]))}</div>'
            f'{gauge(d["cur"], d["r_lt"], d["c_gt"])}'
            f'<div class="tag {"v" if d["tag"] == "V" else "r"}">[{d["tag"]}] {esc(d["asof"])}'
            f'{" · " + str(d["sessions"]) + "-session rule" if d["sessions"] > 1 else ""}</div>'
            f'</div>')

    # calendar rows: next 90 days, plus load-bearing beyond; month precision honest (F9)
    rows = []
    for e in cal:
        d = date.fromisoformat(e["date"])
        delta = (d - today).days
        if delta < 0:
            continue
        if delta > 90 and not e.get("load_bearing"):
            continue
        lb = " lb" if e.get("load_bearing") else ""
        month_only = e.get("precision") == "month"
        chip = f"~{delta}d" if month_only else f"+{delta}d"
        when = f' <span style="opacity:.6">({d.strftime("%b %Y")}, month-verified)</span>' if month_only else ""
        rows.append(f'<div class="ev{lb}"><span class="chip">{chip}</span>'
                    f'<div><div class="evname">{esc(e["event"])}{when}</div>'
                    f'<div class="evwatch">{esc(e["watch"])}</div></div></div>')

    # --- thesis stage (declared rules over tracked evidence, baked at build) ---
    auto_rows = [{"id": d["id"], "prox": d["prox"],
                  "status": {"quiet": "quiet", "confirm": "CONFIRM", "refute": "REFUTE"}[d["status"]]}
                 for d in live]
    a = assess_stage(auto_rows, gaps=n_dark)
    if a["terminal"]:
        stage_html = (f'<h2 id="stage">Thesis stage</h2><div class="stagewrap">'
                      f'<div><span class="stamp gold">{esc(a["name"])}</span></div>'
                      f'<div class="stageev">Reopen by setting thesis_status back to OPEN in '
                      f'tripwires.json, with a journal memo.</div></div>')
    else:
        crits = "".join(
            f'<div class="crit{" pass" if ok else ""}" style="transition-delay:{i*55}ms">'
            f'<span class="lvl">S{lvl}</span><span class="mark">{"✦" if ok else "·"}</span>'
            f'<span>{esc(lbl)}</span></div>'
            for i, (lbl, ok, lvl) in enumerate(a["rules"]))
        overlay = f'<div class="overlay">{esc(a["refute_overlay"])}</div>' if a["refute_overlay"] else ""
        bands = ""
        if a["evidence_note"]:
            bands += f'<div class="warnband">Partial evidence — {esc(a["evidence_note"])}.</div>'
        if a["baseline_expired"]:
            bands += ('<div class="warnband">Baseline prior expired unrenewed — floor dropped to 0. '
                      'Renew it with the quarterly memo, or let it stay dropped.</div>')
        stage_html = f"""
<h2 id="stage">Thesis stage</h2>
<div class="stagewrap">
<div class="attrib">The stage taxonomy and rules below are this monitor's construction, not the
report's — the report defines tripwires and dates; the staging is our synthesis, in plain sight.</div>
<button class="assessbtn" id="runassess">Reveal last build's assessment</button>
<div id="stagepanel">
{crits}
<div style="margin-top:16px"><span class="stamp gold">Stage {a["stage"]} · {esc(a["name"])}</span></div>
{bands}{overlay}
<div class="stageev">
<b>Computed {a["computed"]}, baseline floor {a["floor"]} of prior {a["baseline"]}</b> — {esc(a["baseline_note"])}<br>
Confirms: {esc(", ".join(a["confirms"]) or "none")} · Refutes: {esc(", ".join(a["refutes"]) or "none")}<br>
<b>Toward confirm:</b> {esc(a["next_up"])}<br>
<b>Toward refute:</b> {esc(a["refute_path"])}
</div></div></div>"""

    # manual tripwires grouped, with escaped state badges + rendered notes (F13)
    groups: dict[str, list] = {}
    for t in manual:
        groups.setdefault(t["category"], []).append(t)
    manual_html = []
    for gname, items in groups.items():
        def badge(t):
            st = t.get("state")
            if not st:
                return ""
            return (f'<span class="statebadge {esc(st)}">{esc(st)} · '
                    f'{esc(t.get("state_as_of", ""))}</span>')
        def note(t):
            n = t.get("state_note")
            return f'<div class="statenote">“{esc(n)}”</div>' if n else ""
        lis = "".join(
            f'<div class="mt"><div class="mtname">{esc(t["name"])}{badge(t)}</div>'
            f'<div class="mtnow">{esc(t["current"])}</div>'
            f'<div class="mtline"><span class="k c">confirms</span> {esc(t["confirms"])}</div>'
            f'<div class="mtline"><span class="k r">refutes</span> {esc(t["refutes"])}</div>'
            f'{note(t)}</div>'
            for t in items)
        manual_html.append(f'<details><summary>{esc(gname.replace("_", " "))}'
                           f'<span class="n">{len(items)}</span></summary>{lis}</details>')

    journal_html = "".join(
        f'<div class="jrow"><span class="jkind">{esc(e["kind"])}</span>'
        f'<span>{esc(e.get("event",""))} — {esc(e.get("prediction") or e.get("verdict",""))}</span></div>'
        for e in entries) or '<div class="jrow empty">No entries yet. Log a prediction before the next print.</div>'
    if bad_lines:
        journal_html += (f'<div class="jrow empty">{bad_lines} unreadable journal line(s) skipped '
                         f'— check journal.jsonl for a truncated write.</div>')

    banner = ('<div class="preview">UI preview — static values from the 25 Jul 2026 report. '
              'The live page rebuilds every weekday via GitHub Actions.</div>') if sample else ""
    alert_html = "".join(f'<div class="alertline">{esc(x)}</div>' for x in alerts)

    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>The Useful Life of a Bubble — live appendix</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,480;0,9..144,560;1,9..144,400&family=Spline+Sans+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>
<div class="bubbles">{BUBBLES}</div>
<nav class="topnav"><span class="on">Live appendix</span><a href="#stage">Stage</a><a href="thesis.html">Thesis</a></nav>
<div class="eyebrow">Live appendix · Section 10</div>
<div class="masthead">The Useful Life<br>of a <em>Bubble</em></div>
<div class="rule"></div>
<div class="stamp {stamp_cls}">{stamp}</div>
<div class="stampdate">checked {today.isoformat()}</div>
{alert_html}{pulse}{banner}
<h2>Credit dials — auto-checked daily</h2>
<div class="grid">{"".join(cards)}</div>
{stage_html}
<h2>Dated calendar</h2>
<div class="timeline">{"".join(rows)}</div>
<h2>Filing tripwires — event-day reads</h2>
{"".join(manual_html)}
<h2>Journal</h2>
{journal_html}
<footer><b>Rule 10.7:</b> read the refutation column first. Every figure is fetched, never
recalled — <b>[V]</b> fetched · <b>[R]</b> report value · <b>[G]</b> gap. A dial glows before it
crosses — gold toward confirm, blue toward refute — and a crossing or a dark dial finds you by
push.{cov} Research tooling only — not investment advice.</footer>
<script>
const b=document.getElementById('runassess'),sp=document.getElementById('stagepanel');
if(b)b.addEventListener('click',()=>{{sp.classList.add('open');
b.textContent='Assessed at last build — {today}';b.disabled=true;}});
</script>
</body></html>"""


THESIS_PARA = """The AI infrastructure buildout is not one trade. It is two, and the market is
pricing them as though they were the same thing. The hyperscalers — Microsoft, Alphabet, Amazon,
Meta — are spending enormous sums out of enormous cash flows against contracted revenue that is
real, audited and accelerating, and four of the six largest buyers of AI compute are still in net
cash. That trade is defensible. The periphery — Oracle, CoreWeave, the private-credit-funded
developers, the special-purpose vehicles, and the labs whose finances are not disclosed at all —
is doing something structurally different: financing a decade-length asset with four-year money,
against backlog rather than revenue, using accounting elections that keep roughly $863 billion of
signed obligations off six balance sheets, in a web of arrangements where the same institutions
are simultaneously investor, supplier and customer to one another. The risk is not that the AI
buildout fails. The risk is that the second trade is being financed at the credit quality of the
first, and that when it separates, it will separate at the vehicle level, not the parent level,
where almost nobody is looking."""


def render_thesis() -> str:
    pdf_exists = (ROOT / "docs" / "thesis.pdf").exists()
    pdf = ('<a class="pdfbtn" href="thesis.pdf">Open the full report — PDF</a>' if pdf_exists
           else '<div class="preview">Place the report at docs/thesis.pdf and rebuild.</div>')
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark"><title>The Useful Life of a Bubble — thesis</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,480;0,9..144,560;1,9..144,400&family=Spline+Sans+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{CSS}</style></head>
<body>
<nav class="topnav"><a href="index.html">Live appendix</a><a href="index.html#stage">Stage</a><span class="on">Thesis</span></nav>
<div class="eyebrow">The document · 25 July 2026</div>
<div class="masthead">The Useful Life<br>of a <em>Bubble</em></div>
<div class="rule"></div>
<div class="thesisbody">
<div class="sec">The thesis in one paragraph — §1.1</div>
<p>{esc(THESIS_PARA)}</p>
{pdf}
<div class="sec">How this site relates</div>
<p>The live appendix tracks Section 10 of the report: six credit dials checked daily
against FRED, twenty-three filing tripwires read by hand on event days, the dated
calendar through mid-2028, and a stage assessment computed from declared rules —
with the refutation conditions given equal weight throughout, per the report's own
Rule 10.7. The stage taxonomy is the monitor's construction, not the report's.</p>
</div>
<footer>Research tooling only — not investment advice.</footer>
</body></html>"""


def main() -> None:
    sample = "--sample" in sys.argv
    if not sample and not FRED_KEY:
        print("No FRED_API_KEY — building in gap mode (cards show [G]); use --sample for the UI preview.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(sample))
    (ROOT / "docs" / "thesis.html").write_text(render_thesis())
    print(f"Wrote {OUT} + thesis.html ({'sample preview' if sample else 'live'})")


if __name__ == "__main__":
    main()
