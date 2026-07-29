"""
build_dashboard.py — renders the public site into docs/:

  index.html    the dials ("Now")          record.html   predictions vs results
  start.html    orientation for new readers log.html      how entries get written
  thesis.html   the claim, verbatim        glossary.html  the field guide

Design language: "midnight prospectus" (Fraunces serif numerals, champagne-gold
accent, deep midnight field) — with the 29 Jul 2026 novice-first legibility pass:
every number wears a plain-English line; data stays mono, prose goes sans
(Spline Sans); status color never carries meaning alone (words + position + rails
travel with it); alarm coral appears only when something is actually alarming.
Post red-team invariants intact: cards warm toward confirm AND cool toward refute
(F11), gauges show distance to both rails, the stamp counts dark dials as loudly
as alerts (F5c), gap cards show the actual error (F12), and every status comes
from the same server.evaluate() the cron uses (F1).

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

from glossary import GLOSSARY, INTRO
from server import (FRED_KEY, fred_latest, spread_window, evaluate, assess_stage,
                    STAGE_NAMES, _load, TRIPWIRES_FILE, CALENDAR_FILE, JOURNAL_FILE)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "docs" / "index.html"
REPO = "https://github.com/contofalskyR/bubble-monitor"

# Report values as of 25 Jul 2026 — used only in --sample preview mode
DIAL_CODE = {"credit.hy_oas": "HY", "credit.ccc_oas": "CCC",
             "credit.dispersion": "CCC−HY", "credit.bbb_oas": "BBB",
             "credit.ig_oas": "IG", "credit.ust10y": "10Y"}

SAMPLE_END = {"BAMLH0A0HYM2": 2.77, "BAMLH0A3HYC": 9.91, "BAMLC0A4CBBB": 0.98,
              "BAMLC0A0CM": 0.79, "DGS10": 4.71}

# Which glossary term defines each dial — powers the tap/hover tip on card names
CARD_TERM = {"credit.hy_oas": "High-yield (HY)", "credit.ccc_oas": "CCC",
             "credit.dispersion": "Dispersion (CCC minus HY)", "credit.bbb_oas": "BBB",
             "credit.ig_oas": "Investment grade (IG)", "credit.ust10y": "10-year Treasury"}

# Plain-English one-liner per auto dial — the novice layer (29 Jul legibility pass)
PLAIN = {
    "credit.hy_oas": "The extra yield junk-rated borrowers pay over Treasuries — "
                     "the market's broad fear gauge.",
    "credit.ccc_oas": "What the riskiest tier of borrowers pays. Credit stress "
                      "shows up here first.",
    "credit.dispersion": "The gap between the riskiest credit and ordinary junk. "
                         "Separation, not general panic — the thesis's key number.",
    "credit.bbb_oas": "The cheapest investment-grade tier — the first place a "
                      "downgrade wave would register.",
    "credit.ig_oas": "What blue-chip borrowers pay. If this stays calm while the "
                     "periphery cracks, that IS the thesis.",
    "credit.ust10y": "The risk-free anchor. Higher for longer squeezes everyone "
                     "who financed long assets with short money.",
}


# Concrete, report-anchored example for every declared stage rule — display
# layer only; the rules themselves live in server.assess_stage(), the single
# source of truth. Keys must match the rule labels exactly (selftest enforces
# full coverage, so a relabeled rule fails the build instead of silently
# losing its example).
STAGE_EXAMPLES = {
    "HY index crossed 4.50 (systemic repricing)":
        "Example: high-yield OAS closes above 4.50 and stays there for 10 straight "
        "sessions — junk borrowing costs at panic levels versus ~2.8 in the report. "
        "At that point the whole market is repricing, not just the periphery.",
    "2+ vehicle-level binary events confirmed":
        "Example: CoreWeave exercises an equity cure after the 28 Oct window closes "
        "AND Oracle cancels not-yet-commenced leases — two separate financing "
        "vehicles breaking. This is the shape the thesis says the ending takes.",
    "A vehicle-level binary event confirmed (cures / liquidity / lease cancellation)":
        "Example: any one of — an equity cure used after 28 Oct 2026, CoreWeave cash "
        "under 0.25x of current debt with no raise completed, or Oracle's "
        "not-yet-commenced leases dropping over 10% in a quarter with no matching "
        "right-of-use increase (which would mean cancellation).",
    "3+ periphery tripwires confirmed":
        "Example: Oracle converting under 10% of its contracted revenue within a "
        "year, CoreWeave backlog declining sequentially, and NVIDIA's top-3 "
        "receivables past 70% with rising DSO — three periphery wires at once.",
    "Any credit dial crossed its confirm threshold":
        "Example: CCC OAS closing above 13.00, or the CCC−HY gap above 9.00pp — any "
        "of the six FRED dials actually crossing its coral rail on the Now page.",
    "3+ confirms across all categories":
        "Example: Vertiv keeps its backlog undisclosed, Meta's commitments decline, "
        "and NVIDIA's supply commitments drop over 15% — three confirmed wires "
        "anywhere on the board, in any mix.",
    "2+ dials at 85%+ of the way to confirm":
        "Example: dispersion at 8.6pp and CCC at 12.4 — both pressed to within 15% "
        "of their coral rails without crossing. Pressure without the print.",
    "First confirm anywhere":
        "Example: a single wire anywhere goes to confirm — say Vertiv stays silent "
        "on its backlog again. One is enough to lift the computed stage off zero.",
    "Dispersion 50%+ of the way to confirm":
        "Example: the CCC−HY gap at 7.50pp — halfway from its 6.00 refute rail to "
        "its 9.00 confirm rail. The report's 25 Jul value, 7.14, is 38% of the way.",
    "Any dial running hot (70%+ to confirm)":
        "Example: any dial glowing gold (“warm”) on the Now page — 70%+ of the "
        "distance from its refute rail to its confirm rail. Attention, not evidence.",
}


def esc(s) -> str:
    return html.escape(str(s))


def tip_span(label: str, tip: str) -> str:
    """A term with a tap/hover definition; positioning JS flips the tip to
    whichever side of the term has room."""
    return (f'<span class="dfn" role="button" tabindex="0" '
            f'data-tip="{esc(tip)}">{esc(label)}</span>')


# ---------------------------------------------------------------- glossary tips
def _tipdef(label: str) -> str | None:
    """Find a glossary definition for an inline term: exact match first, then
    shortest term that starts with the label. Returns None when absent — a
    missing tip renders as plain text, never a broken span."""
    lab = label.strip().lower()
    cands = []
    for entries in GLOSSARY.values():
        for term, definition in entries:
            tl = term.strip().lower()
            if tl == lab:
                return definition
            if tl.startswith(lab):
                cands.append((len(term), definition))
    return min(cands)[1] if cands else None


def dfn(label: str, term: str | None = None) -> str:
    """Wrap a term with a tap-to-reveal definition pulled from the glossary."""
    d = _tipdef(term or label)
    return tip_span(label, d) if d else esc(label)


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


def reading(status: str, prox: float, sessions: int) -> str:
    """The plain-language state line on every dial — status word + what it means.
    The word travels with the color, so color never carries meaning alone."""
    if status == "confirm":
        word, cls = "CONFIRMED", "rc"
        rest = "crossed the thesis-right rail"
        rest += f" for all {sessions} sessions" if sessions > 1 else ""
    elif status == "refute":
        word, cls = "REFUTED", "rr"
        rest = "crossed the thesis-wrong rail — evidence against the thesis"
    elif prox >= 0.7:
        word, cls = "warm", "rw"
        rest = "drifting toward the thesis-right rail"
    elif prox <= 0.3:
        word, cls = "calm", "rq"
        rest = "sitting nearer the thesis-wrong rail"
    else:
        word, cls = "calm", "rq"
        rest = "mid-band, far from both rails"
    return f'<div class="reading {cls}"><b>{word}</b> — {rest}</div>'


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
:root{--bg:#0a0d14;--panel:rgba(255,255,255,.032);--line:rgba(255,255,255,.095);
--text:#ece7dc;--ink:#c6cedd;--mut:#aab4c7;--gold:#e3c47f;--confirm:#f4694b;
--refute:#7cb3ff;--quiet:#9db894;
--sans:"Spline Sans",-apple-system,"Segoe UI",system-ui,sans-serif;
--mono:"Spline Sans Mono",ui-monospace,"SF Mono",Menlo,monospace;
--serif:"Fraunces","Iowan Old Style",Georgia,serif}
*{box-sizing:border-box;margin:0}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);
font:15.5px/1.5 var(--mono);
padding:26px 18px 56px;max-width:700px;margin:0 auto;font-variant-numeric:tabular-nums;
position:relative;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:-1;
background:radial-gradient(90% 42% at 50% -6%,#18213a 0%,rgba(24,33,58,0) 68%)}
.bubbles{position:absolute;inset:0 0 auto 0;height:340px;overflow:hidden;pointer-events:none;z-index:-1}
.bubbles i{position:absolute;bottom:-24px;border-radius:50%;
border:1px solid rgba(227,196,127,.16);background:rgba(227,196,127,.03);
animation:rise linear infinite}
@keyframes rise{to{transform:translateY(-420px);opacity:0}}
.topnav{display:flex;gap:6px 16px;flex-wrap:wrap;justify-content:flex-end;font-size:11.5px;
text-transform:uppercase;letter-spacing:.14em;margin-bottom:18px}
.topnav a{color:var(--mut);text-decoration:none;padding:2px 0}
.topnav a:hover{color:var(--gold)}
.topnav .on{color:var(--gold);border-bottom:1px solid rgba(227,196,127,.5);padding:2px 0}
.eyebrow{color:var(--gold);text-transform:uppercase;letter-spacing:.26em;font-size:11px;opacity:.85}
.masthead{font-family:var(--serif);font-weight:560;
font-size:34px;line-height:1.08;margin:8px 0 2px;letter-spacing:.1px}
.masthead em{font-style:italic;color:var(--gold);font-weight:480}
.standfirst{font-family:var(--sans);font-size:14.5px;line-height:1.65;color:var(--ink);
margin:10px 0 0;max-width:60ch}
.standfirst a{color:var(--gold);text-decoration:none;border-bottom:1px dotted rgba(227,196,127,.6)}
.rule{height:1px;background:linear-gradient(90deg,var(--gold),rgba(227,196,127,0));margin:14px 0 18px;opacity:.5}
.stamp{display:inline-block;position:relative;padding:8px 18px;border:1.5px solid var(--quiet);
color:var(--quiet);transform:rotate(-1.2deg);text-transform:uppercase;letter-spacing:.18em;
font-size:12.5px;border-radius:5px;background:rgba(157,184,148,.05)}
.stamp::after{content:"";position:absolute;inset:3px;border:1px solid currentColor;opacity:.35;border-radius:3px}
.stamp.hot{border-color:var(--confirm);color:var(--confirm);background:rgba(244,105,75,.06)}
.stamp.dark{border-color:var(--gold);color:var(--gold);background:rgba(227,196,127,.05)}
.stamp.gold{border-color:var(--gold);color:var(--gold);background:rgba(227,196,127,.05)}
.stampdate{color:var(--mut);font-size:11.5px;margin:8px 0 0}
.nowline{font-family:var(--sans);font-size:15px;line-height:1.65;color:var(--ink);
margin:14px 0 2px;max-width:62ch}
.nowline b{color:var(--text);font-weight:600}
.pulse{display:flex;gap:10px;margin:18px 0 4px;flex-wrap:wrap}
.pcell{flex:1;min-width:150px;background:var(--panel);border:1px solid var(--line);
border-radius:10px;padding:10px 12px}
.pk{font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--mut)}
.pv{font-size:13.5px;margin-top:3px}
.pv.hot{color:var(--confirm)}.pv.calm{color:var(--quiet)}.pv.gold{color:var(--gold)}.pv.cool{color:var(--refute)}
.psub{font-family:var(--sans);font-size:11.5px;color:var(--mut);margin-top:5px;line-height:1.5}
.alertline{color:var(--confirm);font-size:13.5px;margin:3px 0}
.preview{border:1px dashed var(--gold);color:var(--gold);font-size:12.5px;padding:9px 12px;
margin:16px 0;border-radius:8px;background:rgba(227,196,127,.04);font-family:var(--sans)}
h2{font-size:12px;text-transform:uppercase;letter-spacing:.2em;color:var(--mut);
margin:34px 0 12px;font-weight:500;display:flex;align-items:center;gap:10px}
h2::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--gold);opacity:.7;flex-shrink:0}
h2::after{content:"";flex:1;height:1px;background:var(--line)}
.secnote{font-family:var(--sans);font-size:13px;line-height:1.65;color:var(--mut);
margin:-4px 0 14px;max-width:62ch}
.howto{border:1px solid var(--line);background:var(--panel);border-radius:12px;
padding:12px 14px;margin:0 0 14px;font-family:var(--sans);font-size:13px;line-height:1.7;color:var(--ink)}
.howto b.c{color:var(--confirm);font-weight:600}.howto b.r{color:var(--refute);font-weight:600}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;
padding:14px 14px 12px;transition:border-color .3s}
/* no backdrop-filter on .card: it would make the card the containing block for
   position:fixed, throwing every glossary tip inside a card off-screen */
.card.warm{border-color:rgba(227,196,127,.4);box-shadow:0 0 30px -10px rgba(227,196,127,.35)}
.card.cool{border-color:rgba(124,179,255,.35);box-shadow:0 0 30px -12px rgba(124,179,255,.3)}
.card.confirm{border-color:rgba(244,105,75,.55);box-shadow:0 0 34px -8px rgba(244,105,75,.4)}
.card.refute{border-color:rgba(124,179,255,.5);box-shadow:0 0 34px -8px rgba(124,179,255,.35)}
.chead{display:flex;justify-content:space-between;align-items:baseline;gap:6px}
.tick{font-size:16px;font-weight:500;color:var(--text);letter-spacing:.08em;margin-bottom:2px}
.cname{font-size:12.5px;color:var(--mut);letter-spacing:.03em;line-height:1.35}
.delta{font-size:11px;padding:2px 8px;border-radius:99px;border:1px solid var(--line);
white-space:nowrap;flex-shrink:0;color:var(--mut)}
.plain{font-family:var(--sans);font-size:12.5px;line-height:1.6;color:var(--mut);margin:7px 0 0}
.val{font-family:var(--serif);font-weight:560;font-size:33px;margin:4px 0 2px;letter-spacing:.3px}
.card.confirm .val{color:var(--confirm)}.card.refute .val{color:var(--refute)}
.reading{font-family:var(--sans);font-size:12.5px;line-height:1.55;color:var(--ink);margin:2px 0 4px}
.reading b{font-weight:600;letter-spacing:.04em}
.reading.rc b{color:var(--confirm)}.reading.rr b{color:var(--refute)}
.reading.rw b{color:var(--gold)}.reading.rq b{color:var(--quiet)}
.spark{height:34px;margin:4px 0 6px}.spark svg{width:100%;height:34px;display:block}
.gauge{margin-top:2px}
.gtrack{position:relative;height:3px;border-radius:2px;
background:linear-gradient(90deg,rgba(124,179,255,.55),rgba(150,160,181,.25) 42%,rgba(227,196,127,.35) 72%,rgba(244,105,75,.6))}
.gdot{position:absolute;top:-3.5px;width:10px;height:10px;border-radius:50%;
background:var(--text);transform:translateX(-50%);box-shadow:0 0 10px rgba(236,231,220,.7)}
.gmeta{display:flex;justify-content:space-between;font-size:11px;margin-top:6px;letter-spacing:.02em}
.gmeta span{white-space:nowrap}
.gr{color:var(--refute);opacity:.9}.gc{color:var(--confirm);opacity:.9}
.tag{font-size:11.5px;margin-top:9px;letter-spacing:.05em}
.tag.v{color:var(--quiet)}.tag.r,.tag.g{color:var(--gold)}
.gapnote{font-size:12px;color:var(--mut);margin-top:6px;line-height:1.55;word-break:break-word;
font-family:var(--sans)}
.gaperr{color:var(--gold);font-family:var(--mono)}
.timeline{position:relative;padding-left:22px}
.timeline::before{content:"";position:absolute;left:6px;top:6px;bottom:6px;width:1px;
background:linear-gradient(rgba(227,196,127,.5),var(--line) 30%,rgba(255,255,255,0))}
.ev{position:relative;display:flex;gap:12px;padding:11px 0;border-bottom:1px solid rgba(255,255,255,.05)}
.ev::before{content:"";position:absolute;left:-19.5px;top:17px;width:7px;height:7px;
border-radius:50%;background:var(--mut)}
.ev.lb::before{width:9px;height:9px;left:-20.5px;background:var(--gold);
box-shadow:0 0 12px rgba(227,196,127,.8)}
.chip{color:var(--gold);min-width:52px;font-size:13px;padding-top:1px}
.evname{font-size:14.5px;font-family:var(--serif);font-weight:480;letter-spacing:.2px}
.ev.lb .evname{color:var(--gold)}
.evwatch{font-size:12.5px;color:var(--mut);margin-top:3px;line-height:1.55;font-family:var(--sans)}
details{border:1px solid var(--line);border-radius:12px;margin-bottom:10px;
background:var(--panel);overflow:hidden}
summary{padding:12px 14px;cursor:pointer;text-transform:capitalize;font-size:13.5px;
display:flex;justify-content:space-between;align-items:center;gap:8px;list-style:none}
summary::-webkit-details-marker{display:none}
summary .n{color:var(--gold);font-size:11.5px;white-space:nowrap}
.schip{font-size:10.5px;padding:2px 8px;border-radius:99px;margin-left:6px;white-space:nowrap}
.schip.c{color:var(--confirm);border:1px solid rgba(244,105,75,.4)}
.schip.r{color:var(--refute);border:1px solid rgba(124,179,255,.4)}
.mt{padding:11px 14px;border-top:1px solid rgba(255,255,255,.05)}
.mtname{font-size:14px;font-family:var(--serif);font-weight:480}
.mtnow{font-size:12.5px;color:var(--mut);margin:4px 0 6px;line-height:1.5;font-family:var(--sans)}
.mtline{font-size:12px;margin:3px 0;line-height:1.5}
.statenote{font-size:11.5px;color:var(--gold);margin:3px 0 0;line-height:1.5;font-style:italic}
.k{display:inline-block;width:72px;text-transform:uppercase;letter-spacing:.1em;font-size:9.5px}
.k.c{color:var(--confirm)}.k.r{color:var(--refute)}
.jrow{display:flex;gap:12px;font-size:12.5px;padding:8px 2px;border-bottom:1px solid rgba(255,255,255,.05)}
.jkind{color:var(--gold);text-transform:uppercase;font-size:10px;min-width:64px;
letter-spacing:.12em;padding-top:3px}
.jrow.empty{color:var(--mut);font-family:var(--sans)}
.jmore{font-family:var(--sans);font-size:13px;margin-top:12px}
.jmore a{color:var(--gold);text-decoration:none;border-bottom:1px dotted rgba(227,196,127,.6)}
footer{margin-top:40px;color:var(--mut);font-size:12.5px;line-height:1.7;
border-top:1px solid var(--line);padding-top:16px;font-family:var(--sans)}
footer b{color:var(--gold);font-weight:500}
footer a{color:var(--gold);text-decoration:none;border-bottom:1px dotted rgba(227,196,127,.6)}
.stagewrap{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 16px}
.attrib{font-size:12px;color:var(--mut);margin-bottom:12px;line-height:1.6;font-family:var(--sans)}
.assessbtn{font:inherit;font-size:12px;letter-spacing:.16em;text-transform:uppercase;
color:var(--gold);background:rgba(227,196,127,.07);border:1px solid rgba(227,196,127,.45);
border-radius:8px;padding:11px 20px;cursor:pointer;transition:all .25s}
.assessbtn:hover{background:rgba(227,196,127,.14);box-shadow:0 0 24px -8px rgba(227,196,127,.5)}
.assessbtn:disabled{opacity:.55;cursor:default;box-shadow:none}
#stagepanel{display:none;margin-top:16px}
#stagepanel.open{display:block}
.crit{display:flex;gap:10px;font-size:12.5px;padding:6px 0;border-bottom:1px solid rgba(255,255,255,.05);
opacity:0;transform:translateY(6px);transition:opacity .4s ease,transform .4s ease}
.open .crit{opacity:1;transform:none}
.crit .lvl{color:var(--mut);min-width:26px;font-size:10.5px;padding-top:2px}
.crit .mark{min-width:16px;color:var(--mut)}.crit.pass .mark{color:var(--gold)}
.crit.pass{color:var(--text)}.crit:not(.pass){color:var(--mut)}
.stageev{font-size:12.5px;color:var(--mut);margin-top:12px;line-height:1.7;font-family:var(--sans)}
.stageev b{color:var(--gold);font-weight:500}
.overlay{border:1px solid rgba(124,179,255,.45);color:var(--refute);font-size:12.5px;
padding:9px 12px;border-radius:8px;margin-top:12px;background:rgba(124,179,255,.05);font-family:var(--sans)}
.warnband{border:1px solid rgba(227,196,127,.5);color:var(--gold);font-size:12.5px;
padding:9px 12px;border-radius:8px;margin-top:12px;background:rgba(227,196,127,.05);font-family:var(--sans)}
.pdfbtn{display:inline-block;font-size:12.5px;letter-spacing:.14em;text-transform:uppercase;
color:var(--bg);background:var(--gold);border-radius:8px;padding:13px 24px;text-decoration:none;
margin:18px 0;font-weight:500}
.thesisbody{font-size:15px;line-height:1.75;color:var(--text);font-family:var(--sans)}
.thesisbody p{margin:14px 0}.thesisbody .sec{color:var(--gold);font-size:11px;
text-transform:uppercase;letter-spacing:.2em;margin-top:26px;font-family:var(--mono)}
.dfn{border-bottom:1px dotted rgba(227,196,127,.65);cursor:help;position:relative}
.dfn::after{content:attr(data-tip);position:fixed;left:var(--tipx,12px);top:var(--tipy,auto);
width:min(320px,76vw);background:#141b2c;border:1px solid rgba(227,196,127,.35);
padding:10px 12px;border-radius:8px;font-family:var(--sans);font-size:12.5px;line-height:1.6;
color:var(--ink);display:none;z-index:6;text-transform:none;letter-spacing:0;font-weight:400;
box-shadow:0 12px 30px -10px rgba(0,0,0,.7)}
.dfn.show::after{display:block}
.dfn.flipy::after{top:auto;bottom:var(--tipb,auto)}
@media (hover:hover){.dfn:hover::after{display:block}}
.plainstage{font-family:var(--sans);font-size:13px;line-height:1.65;color:var(--ink);margin-top:12px}
.plainstage b{color:var(--text)}
.tally{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0 4px}
.tcell{flex:1;min-width:96px;background:var(--panel);border:1px solid var(--line);
border-radius:10px;padding:10px 12px;text-align:left}
.tnum{font-family:var(--serif);font-weight:560;font-size:26px}
.tcell.tr .tnum{color:var(--quiet)}.tcell.tw .tnum{color:var(--confirm)}.tcell.tm .tnum{color:var(--gold)}
.rc{background:var(--panel);border:1px solid var(--line);border-radius:14px;
padding:16px;margin-bottom:12px}
.rhead{display:flex;justify-content:space-between;gap:8px;align-items:baseline;flex-wrap:wrap}
.rkind{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--gold);
border:1px solid rgba(227,196,127,.4);border-radius:99px;padding:2px 9px;white-space:nowrap}
.rts{font-size:11px;color:var(--mut)}
.revent{font-family:var(--serif);font-weight:480;font-size:18px;margin:8px 0 6px}
.rtext{font-family:var(--sans);font-size:14px;line-height:1.65;color:var(--text)}
.why{border:none;background:none;margin:6px 0 0}
.why summary{padding:4px 0;font-size:12px;color:var(--mut);text-transform:none;font-family:var(--sans)}
.why .rtext{color:var(--ink);font-size:13px;padding:4px 0 2px}
.result{border-top:1px dashed rgba(255,255,255,.12);margin-top:12px;padding-top:12px}
.verdict{display:inline-block;font-size:11px;letter-spacing:.14em;text-transform:uppercase;
border-radius:99px;padding:3px 11px;font-weight:500;margin-right:8px}
.verdict.v-right{color:var(--quiet);border:1.5px solid rgba(157,184,148,.55)}
.verdict.v-wrong{color:var(--confirm);border:1.5px solid rgba(244,105,75,.55)}
.verdict.v-mixed{color:var(--gold);border:1.5px solid rgba(227,196,127,.55)}
.await{display:inline-block;font-family:var(--sans);font-size:12px;color:var(--mut);
border:1px dashed rgba(255,255,255,.2);border-radius:99px;padding:3px 11px}
.lesson{font-family:var(--sans);font-size:13px;line-height:1.6;color:var(--ink);
font-style:italic;margin-top:8px}
.prov{border:1px solid var(--line);background:var(--panel);border-radius:12px;
padding:12px 14px;margin:18px 0;font-family:var(--sans);font-size:13px;line-height:1.65;color:var(--ink)}
.prov a{color:var(--gold);text-decoration:none;border-bottom:1px dotted rgba(227,196,127,.6)}
.method{background:var(--panel);border:1px solid var(--line);border-radius:14px;
padding:16px;margin-bottom:12px}
.mhead{display:flex;gap:10px;align-items:baseline}
.mnum{font-family:var(--serif);font-size:22px;color:var(--gold);font-weight:560}
.mtitle{font-family:var(--serif);font-size:17px;font-weight:480}
.mbody{font-family:var(--sans);font-size:13.5px;line-height:1.7;color:var(--ink);margin-top:8px}
.mbody code{font-family:var(--mono);font-size:12px;color:var(--gold);background:rgba(227,196,127,.08);
padding:1px 6px;border-radius:5px}
.mbody a,.rtext a,.secnote a,.startbody a,.thesisbody a{color:var(--gold);text-decoration:none;
border-bottom:1px dotted rgba(227,196,127,.6)}
.gobtn{display:inline-block;font-size:12px;letter-spacing:.14em;text-transform:uppercase;
color:var(--bg);background:var(--gold);border-radius:8px;padding:11px 18px;text-decoration:none;
margin:10px 0 2px;font-weight:500;font-family:var(--mono)}
.fieldrow{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,.05);
font-family:var(--sans);font-size:13px;line-height:1.55}
.fieldrow code{font-family:var(--mono);font-size:11.5px;color:var(--gold);min-width:92px;padding-top:1px}
.twid{font-family:var(--mono);font-size:11.5px;color:var(--gold);background:rgba(227,196,127,.08);
padding:1px 7px;border-radius:5px}
.idrow{display:flex;gap:10px;padding:6px 0;font-size:12.5px;font-family:var(--sans);
color:var(--ink);align-items:baseline;flex-wrap:wrap}
.startbody{font-family:var(--sans);font-size:15px;line-height:1.75;color:var(--text)}
.startbody p{margin:12px 0}
.startbody .railword-c{color:var(--confirm);font-weight:600}
.startbody .railword-r{color:var(--refute);font-weight:600}
.callout{border:1px solid rgba(227,196,127,.4);background:rgba(227,196,127,.05);
border-radius:12px;padding:14px 16px;margin:16px 0;font-family:var(--sans);
font-size:14px;line-height:1.7;color:var(--ink)}
.callout b{color:var(--gold);font-weight:600}
@media (max-width:600px){
  .grid{grid-template-columns:1fr}
  .val{font-size:42px}
  .spark,.spark svg{height:44px}
  .cname{font-size:13px}
  body{font-size:16px}
  .topnav{justify-content:flex-start}
}
@media (max-width:390px){.masthead{font-size:29px}}
.gfilter{width:100%;padding:13px 14px;background:var(--panel);border:1px solid var(--line);
color:var(--text);font:inherit;font-size:16px;border-radius:10px;margin:14px 0 6px}
.gfilter::placeholder{color:var(--mut)}
.gent{padding:13px 0;border-bottom:1px solid rgba(255,255,255,.06)}
.gterm{font-family:var(--serif);font-weight:480;font-size:16.5px;letter-spacing:.2px}
.gdef{font-size:14px;line-height:1.7;color:var(--ink);margin-top:5px;font-family:var(--sans)}
.gintro{margin:6px 0 4px}
.gintro h3{font-family:var(--serif);font-weight:480;font-size:15.5px;color:var(--gold);margin:18px 0 6px}
.gintro p{font-size:14px;line-height:1.7;color:var(--ink);font-family:var(--sans)}
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

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@'
         '0,9..144,400;0,9..144,480;0,9..144,560;1,9..144,400&family=Spline+Sans+Mono:'
         'wght@400;500&family=Spline+Sans:wght@400;500;600&display=swap" rel="stylesheet">')

# tap/hover definitions. The tip is position:fixed and PLACED BY JS — anchoring
# an absolute tip to a line-wrapped inline span is browser-fragile (it pins to a
# single line fragment and can leave the screen). tipPlace clamps the tip inside
# the viewport horizontally and opens it below the term, or above (flipy) when
# the term sits in the lower part of the screen. Scroll dismisses; Esc dismisses.
TIP_JS = """
function tipPlace(t){
  var r=t.getBoundingClientRect();
  var w=Math.min(320,window.innerWidth*0.76);
  var x=Math.max(8,Math.min(r.left,window.innerWidth-w-8));
  t.style.setProperty('--tipx',x+'px');
  if(r.bottom>window.innerHeight-220){
    t.classList.add('flipy');
    t.style.setProperty('--tipb',(window.innerHeight-r.top+8)+'px');
  }else{
    t.classList.remove('flipy');
    t.style.setProperty('--tipy',(r.bottom+8)+'px');
  }
}
var tipAnchorY=0;
function tipCloseAll(){document.querySelectorAll('.dfn.show').forEach(function(d){d.classList.remove('show')});}
document.addEventListener('mouseover',function(e){
  var t=e.target.closest&&e.target.closest('.dfn');if(t)tipPlace(t);});
document.addEventListener('click',function(e){
  var t=e.target.closest&&e.target.closest('.dfn');
  document.querySelectorAll('.dfn.show').forEach(function(d){if(d!==t)d.classList.remove('show')});
  if(t){tipPlace(t);t.classList.toggle('show');tipAnchorY=window.scrollY;}});
document.addEventListener('scroll',function(){
  if(Math.abs(window.scrollY-tipAnchorY)>24)tipCloseAll();},{passive:true});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape')tipCloseAll();
  if(e.key==='Enter'&&e.target.classList&&e.target.classList.contains('dfn')){tipPlace(e.target);e.target.classList.toggle('show');}});
"""

NAV_ITEMS = [("start.html", "Start here", "start"), ("index.html", "Now", "now"),
             ("record.html", "Record", "record"), ("log.html", "Log", "log"),
             ("glossary.html", "Glossary", "glossary"), ("thesis.html", "Thesis", "thesis")]


def nav(active: str) -> str:
    parts = []
    for href, label, key in NAV_ITEMS:
        if key == active:
            parts.append(f'<span class="on">{label}</span>')
        else:
            parts.append(f'<a href="{href}">{label}</a>')
    return f'<nav class="topnav">{"".join(parts)}</nav>'


def page(title: str, active: str, body: str, extra_js: str = "") -> str:
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="dark">
<title>{esc(title)}</title>
{FONTS}
<style>{CSS}</style></head>
<body>
{nav(active)}
{body}
<script>{TIP_JS}{extra_js}</script>
</body></html>"""


# --------------------------------------------------------------------- journal
def parse_journal():
    """All journal entries, tolerant of a truncated line (F7). Returns
    (predictions, scores, others, bad_line_count); predictions carry a
    'score' key once paired."""
    preds, scores, others, bad = [], [], [], 0
    if JOURNAL_FILE.exists():
        for ln in JOURNAL_FILE.read_text().strip().splitlines():
            if not ln.strip():
                continue
            try:
                e = json.loads(ln)
            except json.JSONDecodeError:
                bad += 1
                continue
            k = e.get("kind")
            if k == "prediction":
                e["score"] = None
                preds.append(e)
            elif k == "score":
                scores.append(e)
            else:
                others.append(e)
    orphans = []
    for s in scores:
        key = str(s.get("event", "")).strip().lower()
        match = next((p for p in reversed(preds)
                      if str(p.get("event", "")).strip().lower() == key
                      and p["score"] is None), None)
        if match is not None:
            match["score"] = s
        else:
            orphans.append(s)
    return preds, orphans, others, bad


def fmt_ts(e) -> str:
    ts = str(e.get("ts", ""))
    return esc(ts[:16].replace("T", " ") + " UTC") if len(ts) >= 16 else esc(ts)


# ----------------------------------------------------------------------- index
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

    # plain-language state line (novice layer) — mechanical, from the same
    # evaluate() results as everything else; sample data is all-quiet by
    # construction so this can never fabricate urgency in a preview
    quiet_live = [d for d in live if d["status"] == "quiet"]
    nearest = (min(quiet_live, key=lambda d: min(d["prox"], 1 - d["prox"]))
               if quiet_live else None)
    if alerts:
        nowline = (f"<b>Right now:</b> {len(alerts)} dial{'s have' if len(alerts) != 1 else ' has'} "
                   f"crossed a rail — read those cards first, refute rail before confirm, "
                   f"per the house rule.")
    elif n_dark and not live:
        nowline = ("<b>Right now:</b> no dials could be fetched — an outage is a finding, "
                   "not a pass. See the gap notes below.")
    elif nearest is not None:
        gap_note = f" ({n_dark} dial{'s' if n_dark != 1 else ''} dark)" if n_dark else ""
        nm, code = esc(nearest["name"]), DIAL_CODE.get(nearest["id"], "")
        if nearest["prox"] >= 0.5:
            d_c = nearest["c_gt"] - nearest["cur"]
            nowline = (f"<b>Right now:</b> nothing has crossed{gap_note}. The dial closest to "
                       f"either rail is {nm} ({code}), {d_c:g} away from the thesis-<i>right</i> "
                       f"rail — drifting toward confirmation without being there.")
        else:
            d_r = nearest["cur"] - nearest["r_lt"]
            nowline = (f"<b>Right now:</b> nothing has crossed{gap_note}. The dial closest to "
                       f"either rail is {nm} ({code}), just {d_r:g} above the thesis-<i>wrong</i> "
                       f"rail — today's tape argues against the thesis more than for it.")
    else:
        nowline = "<b>Right now:</b> nothing has crossed."

    # pulse strip — symmetric (F11): nearest threshold in EITHER direction
    next_lb = next((e for e in cal if e.get("load_bearing")
                    and date.fromisoformat(e["date"]) >= today), None)
    p1 = (f'<span class="pv hot">{len(alerts)} crossed</span>' if alerts
          else f'<span class="pv gold">{n_dark} dials dark</span>' if n_dark
          else '<span class="pv calm">nothing crossed</span>')
    if nearest is not None:
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
             f'<div class="pcell"><div class="pk">Today</div>{p1}'
             f'<div class="psub">did any dial cross a rail?</div></div>'
             f'<div class="pcell"><div class="pk">Nearest threshold</div>{p2}'
             f'<div class="psub">the dial closest to either rail</div></div>'
             f'<div class="pcell"><div class="pk">Next load-bearing date</div>{p3}'
             f'<div class="psub">the date the thesis must show up on</div></div></div>')

    # how-to legend — the two-rail grammar, stated once, above the dials
    howto = (f'<div class="howto">Every dial runs between two rails. Crossing the '
             f'<b class="c">coral rail (confirm)</b> is evidence the thesis is playing out — '
             f'the thesis-right rail. Crossing the <b class="r">blue rail (refute)</b> is '
             f'evidence it is wrong — the thesis-wrong rail. House rule, from the report: '
             f'{dfn("read the refute side first", "Rule 10.7")}. Values are '
             f'{dfn("OAS", "OAS")} in percentage points, fetched from FRED — '
             f'dotted terms open a definition.</div>')

    # dial cards
    cards = []
    for i, d in enumerate(dials):
        if "gap" in d:
            cards.append(f'<div class="card"><div class="tick">{DIAL_CODE.get(d["id"], "")}</div>'
                         f'<div class="cname">{dfn(d["name"], CARD_TERM.get(d["id"]))}</div>'
                         f'<div class="tag g">{dfn("[G]", "Provenance tags")} no fetch</div>'
                         f'<div class="gapnote"><span class="gaperr">{esc(d["gap"])}</span><br>'
                         f'A dark dial is a finding, not a pass — if this persists, the series '
                         f'may have changed or been withdrawn.</div></div>')
            continue
        halo = (" warm" if d["status"] == "quiet" and d["prox"] >= 0.7
                else " cool" if d["status"] == "quiet" and d["prox"] <= 0.3 else "")
        darrow = "▲" if d["delta"] > 0 else "▼" if d["delta"] < 0 else "·"
        tone = ("#f4694b" if d["status"] == "confirm" or d["prox"] >= 0.7
                else "#7cb3ff" if d["status"] == "refute" or d["prox"] <= 0.3
                else "#e3c47f")
        plain = PLAIN.get(d["id"], "")
        cards.append(
            f'<div class="card {d["status"]}{halo}">'
            f'<div class="chead"><div><div class="tick">{DIAL_CODE.get(d["id"], "")}</div>'
            f'<div class="cname">{dfn(d["name"], CARD_TERM.get(d["id"]))}</div></div>'
            f'<span class="delta">{darrow} {d["delta"]:+g} · {dfn("30 sess", "Session")}</span></div>'
            f'<div class="val">{d["cur"]:g}</div>'
            f'{reading(d["status"], d["prox"], d["sessions"])}'
            f'<div class="spark">{spark_area(d["vals"], str(i), tone, (d["r_lt"], d["c_gt"]))}</div>'
            f'{gauge(d["cur"], d["r_lt"], d["c_gt"])}'
            f'<div class="plain">{esc(plain)}</div>'
            f'<div class="tag {"v" if d["tag"] == "V" else "r"}">{dfn("[" + d["tag"] + "]", "Provenance tags")} {esc(d["asof"])}'
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
            f'<span>{tip_span(lbl, STAGE_EXAMPLES[lbl]) if lbl in STAGE_EXAMPLES else esc(lbl)}</span></div>'
            for i, (lbl, ok, lvl) in enumerate(a["rules"]))
        stages_tip = ("The five stages: "
                      + " · ".join(f"{i} {STAGE_NAMES[i]}" for i in sorted(STAGE_NAMES))
                      + ". The highest rung whose rule is satisfied sets the computed stage; "
                        "a report-derived floor can hold the stamp higher until that prior expires. "
                        "Each rule above carries a concrete example — tap it.")
        review_by = _load(TRIPWIRES_FILE).get("_meta", {}).get("baseline_review_by", "")
        expiry = f" (expires after {esc(review_by)} unless deliberately renewed)" if review_by and a["floor"] else ""
        plain_floor = (f'In plain terms: the satisfied rules above reach <b>Stage {a["computed"]}</b> '
                       f'on their own; the report\'s own July 2026 assessment sets a floor of '
                       f'<b>{a["floor"]}</b>{expiry}; the stamp shows the higher of the two. '
                       f'{tip_span("What the stages mean", stages_tip)}.')
        overlay = f'<div class="overlay">{esc(a["refute_overlay"])}</div>' if a["refute_overlay"] else ""
        bands = ""
        if a["evidence_note"]:
            bands += f'<div class="warnband">Partial evidence — {esc(a["evidence_note"])}.</div>'
        if a["baseline_expired"]:
            bands += ('<div class="warnband">Baseline prior expired unrenewed — floor dropped to 0. '
                      'Renew it with the quarterly memo, or let it stay dropped.</div>')
        stage_html = f"""
<h2 id="stage">Thesis stage</h2>
<div class="secnote">A 0-to-4 answer to "how far along is this thesis?", computed from the
dials and states above by declared rules — tap the button to see which rules fired.</div>
<div class="stagewrap">
<div class="attrib">The stage taxonomy and rules below are this monitor's construction, not the
report's — the report defines tripwires and dates; the staging is our synthesis, in plain sight.</div>
<button class="assessbtn" id="runassess">Reveal last build's assessment</button>
<div id="stagepanel">
{crits}
<div style="margin-top:16px"><span class="stamp gold">Stage {a["stage"]} · {esc(a["name"])}</span></div>
<div class="plainstage">{plain_floor}</div>
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
        n_c = sum(1 for t in items if t.get("state") == "confirm")
        n_r = sum(1 for t in items if t.get("state") == "refute")
        schips = ((f'<span class="schip c">{n_c} confirm</span>' if n_c else "")
                  + (f'<span class="schip r">{n_r} refute</span>' if n_r else ""))
        lis = "".join(
            f'<div class="mt"><div class="mtname">{esc(t["name"])}{badge(t)}</div>'
            f'<div class="mtnow">{esc(t["current"])}</div>'
            f'<div class="mtline"><span class="k c">confirms</span> {esc(t["confirms"])}</div>'
            f'<div class="mtline"><span class="k r">refutes</span> {esc(t["refutes"])}</div>'
            f'{note(t)}</div>'
            for t in items)
        manual_html.append(f'<details><summary>{esc(gname.replace("_", " "))}'
                           f'<span class="n">{schips}{len(items)}</span></summary>{lis}</details>')

    journal_html = "".join(
        f'<div class="jrow"><span class="jkind">{esc(e["kind"])}</span>'
        f'<span>{esc(e.get("event",""))} — {esc(e.get("prediction") or e.get("verdict",""))}</span></div>'
        for e in entries) or '<div class="jrow empty">No entries yet. Log a prediction before the next print.</div>'
    if bad_lines:
        journal_html += (f'<div class="jrow empty">{bad_lines} unreadable journal line(s) skipped '
                         f'— check journal.jsonl for a truncated write.</div>')
    journal_html += ('<div class="jmore"><a href="record.html">Full record — every call, '
                     'scored right or wrong →</a></div>')

    banner = ('<div class="preview">UI preview — static values from the 25 Jul 2026 report. '
              'The live page rebuilds every weekday via GitHub Actions.</div>') if sample else ""
    alert_html = "".join(f'<div class="alertline">{esc(x)}</div>' for x in alerts)

    body = f"""<div class="bubbles">{BUBBLES}</div>
<div class="eyebrow">Live appendix · Section 10</div>
<div class="masthead">The Useful Life<br>of a <em>Bubble</em></div>
<div class="standfirst">A public, timestamped monitor for one credit thesis — checked every
weekday, wrong in public if wrong. New here? <a href="start.html">Start with the
five-minute guide.</a></div>
<div class="rule"></div>
<div class="stamp {stamp_cls}">{stamp}</div>
<div class="stampdate">checked {today.isoformat()}</div>
{alert_html}
<div class="nowline">{nowline}</div>
{pulse}{banner}
<h2>Credit dials — auto-checked daily</h2>
{howto}
<div class="grid">{"".join(cards)}</div>
{stage_html}
<h2>Dated calendar</h2>
<div class="secnote">Dates the report says will force information out — earnings, covenant
tests, filing deadlines. Gold dots are {dfn("load-bearing", "Load-bearing date")}: the thesis
has to show up on them, or it is in trouble.</div>
<div class="timeline">{"".join(rows)}</div>
<h2>Filing tripwires — event-day reads</h2>
<div class="secnote">These cannot be fetched by machine — a human reads the filing on the day
and records confirm, refute, or quiet. No badge means not yet assessed, which is not the same
as safe.</div>
{"".join(manual_html)}
<h2>Journal</h2>
{journal_html}
<footer><b>Rule 10.7:</b> read the refutation column first. Every figure is fetched, never
recalled — <b>[V]</b> fetched live · <b>[R]</b> report value · <b>[G]</b> gap, no data. A dial
glows before it crosses — gold toward confirm, blue toward refute — and a crossing or a dark
dial finds you by push, so a quiet page really does mean quiet.{cov}
New readers: <a href="start.html">the guide</a> explains every convention on this page.
Research tooling only — not investment advice.</footer>"""

    stage_js = ("const b=document.getElementById('runassess'),sp=document.getElementById('stagepanel');"
                "if(b)b.addEventListener('click',()=>{sp.classList.add('open');"
                f"b.textContent='Assessed at last build — {today}';b.disabled=true;}});")
    return page("The Useful Life of a Bubble — live appendix", "now", body, stage_js)


# ---------------------------------------------------------------------- record
def render_record() -> str:
    preds, orphans, others, bad = parse_journal()
    scored = [p for p in preds if p["score"] is not None]
    verdicts = [str(p["score"].get("verdict", "")).lower() for p in scored]
    n_right = verdicts.count("right")
    n_wrong = verdicts.count("wrong")
    n_mixed = verdicts.count("mixed")

    tally = (f'<div class="tally">'
             f'<div class="tcell"><div class="pk">Predictions</div><div class="tnum">{len(preds)}</div></div>'
             f'<div class="tcell"><div class="pk">Scored</div><div class="tnum">{len(scored)}</div></div>'
             f'<div class="tcell tr"><div class="pk">Right</div><div class="tnum">{n_right}</div></div>'
             f'<div class="tcell tw"><div class="pk">Wrong</div><div class="tnum">{n_wrong}</div></div>'
             f'<div class="tcell tm"><div class="pk">Mixed</div><div class="tnum">{n_mixed}</div></div>'
             f'</div>')

    cards = []
    for p in sorted(preds, key=lambda e: str(e.get("ts", "")), reverse=True):
        why = (f'<details class="why"><summary>reasoning at the time</summary>'
               f'<div class="rtext">{esc(p["reasoning"])}</div></details>'
               if p.get("reasoning") else "")
        s = p["score"]
        if s is not None:
            v = str(s.get("verdict", "")).lower()
            vcls = {"right": "v-right", "wrong": "v-wrong", "mixed": "v-mixed"}.get(v, "v-mixed")
            lesson = (f'<div class="lesson">Lesson — {esc(s["lesson"])}</div>'
                      if s.get("lesson") else "")
            result = (f'<div class="result"><span class="verdict {vcls}">{esc(v or "scored")}</span>'
                      f'<span class="rts">scored {fmt_ts(s)}</span>'
                      f'<div class="rtext" style="margin-top:8px"><b>What printed:</b> '
                      f'{esc(s.get("actual", ""))}</div>{lesson}</div>')
        else:
            result = ('<div class="result"><span class="await">awaiting result — '
                      'scored after the print</span></div>')
        cards.append(
            f'<div class="rc"><div class="rhead"><span class="rkind">prediction</span>'
            f'<span class="rts">logged {fmt_ts(p)}{" · via phone" if p.get("via") == "phone" else ""}</span></div>'
            f'<div class="revent">{esc(p.get("event", ""))}</div>'
            f'<div class="rtext">{esc(p.get("prediction", ""))}</div>'
            f'{why}{result}</div>')

    for s in sorted(orphans, key=lambda e: str(e.get("ts", "")), reverse=True):
        v = str(s.get("verdict", "")).lower()
        vcls = {"right": "v-right", "wrong": "v-wrong", "mixed": "v-mixed"}.get(v, "v-mixed")
        cards.append(
            f'<div class="rc"><div class="rhead"><span class="rkind">score</span>'
            f'<span class="rts">logged {fmt_ts(s)}</span></div>'
            f'<div class="revent">{esc(s.get("event", ""))}</div>'
            f'<div class="result" style="border:none;margin:0;padding:6px 0 0">'
            f'<span class="verdict {vcls}">{esc(v or "scored")}</span>'
            f'<div class="rtext" style="margin-top:8px">{esc(s.get("actual", ""))}</div></div></div>')

    for o in sorted(others, key=lambda e: str(e.get("ts", "")), reverse=True):
        cards.append(
            f'<div class="rc"><div class="rhead"><span class="rkind">{esc(o.get("kind", "entry"))}</span>'
            f'<span class="rts">logged {fmt_ts(o)}</span></div>'
            f'<div class="revent">{esc(o.get("event", ""))}</div>'
            f'<div class="rtext">{esc(o.get("text") or o.get("note") or "")}</div></div>')

    if not cards:
        cards.append('<div class="jrow empty">No entries yet. Log a prediction before the next print.</div>')
    if bad:
        cards.append(f'<div class="jrow empty">{bad} unreadable journal line(s) skipped '
                     f'— check journal.jsonl for a truncated write.</div>')

    body = f"""<div class="eyebrow">The record</div>
<div class="masthead">Called in <em>advance</em>,<br>scored in public</div>
<div class="standfirst">Every prediction here was committed to a public git history
<i>before</i> the event printed, then scored — right or wrong — after. Misses stay up:
a record you can edit is not a record.</div>
<div class="rule"></div>
{tally}
<div class="prov">Don't take the timestamps on faith —
<a href="{REPO}/commits/main/journal.jsonl">verify them on GitHub</a>. Every entry is a
commit on GitHub's clock, made before the print it calls.</div>
{"".join(cards)}
<footer>Predictions and scores are written via the <a href="log.html">journal</a> and
rendered exactly as committed. Research tooling only — not investment advice.</footer>"""
    return page("Record — The Useful Life of a Bubble", "record", body)


# ------------------------------------------------------------------------- log
def render_log() -> str:
    manual = [t for t in _load(TRIPWIRES_FILE)["tripwires"] if t["check"]["type"] == "manual"]
    groups: dict[str, list] = {}
    for t in manual:
        groups.setdefault(t["category"], []).append(t)
    idrefs = "".join(
        f'<details><summary>{esc(g.replace("_", " "))}<span class="n">{len(items)}</span></summary>'
        + "".join(f'<div class="mt idrow"><code class="twid">{esc(t["id"])}</code>'
                  f'<span>{esc(t["name"])}</span></div>' for t in items)
        + '</details>'
        for g, items in groups.items())

    fields = f"""
<div class="fieldrow"><code>kind</code><span>what you're logging — <b>prediction</b> before
an event, <b>score</b> after it, or <b>set-state</b> for a filing tripwire.</span></div>
<div class="fieldrow"><code>event</code><span>prediction / score — the event name, e.g.
<i>Meta Q2 2026</i>. Use the same name in both so they pair on the record page.</span></div>
<div class="fieldrow"><code>text</code><span>prediction — your call and reasoning ·
score — what actually printed.</span></div>
<div class="fieldrow"><code>verdict</code><span>score only — <b>right</b>, <b>wrong</b>,
or <b>mixed</b>. Anything else is rejected.</span></div>
<div class="fieldrow"><code>lesson</code><span>score only, optional — what the miss (or hit)
taught you. The most valuable field on the site.</span></div>
<div class="fieldrow"><code>tripwire_id</code><span>set-state only — the dial's id, e.g.
<code>hyper.meta_commitments</code>. Full list below.</span></div>
<div class="fieldrow"><code>state</code><span>set-state only — <b>confirm</b>, <b>refute</b>,
<b>quiet</b>, or <b>clear</b> to remove a state. Auto-fetched FRED dials refuse hand-set
states by design.</span></div>
<div class="fieldrow"><code>note</code><span>set-state only — WHY, with the number you read.
Goes in the public record.</span></div>"""

    body = f"""<div class="eyebrow">Writing to the record</div>
<div class="masthead">Log an <em>entry</em></div>
<div class="standfirst">Three ways to write a prediction, a score, or a tripwire state —
all three end as a git commit, which is what makes the record a record. The site rebuilds
itself about two minutes after any entry lands.</div>
<div class="rule"></div>

<div class="method"><div class="mhead"><span class="mnum">1</span>
<span class="mtitle">From your phone, or any browser — the logging form</span></div>
<div class="mbody">A GitHub form, run on GitHub's machines — it works with the laptop asleep.
Sign in to GitHub, open the form, press <b>Run workflow</b>, fill the fields, run. Your entry
is committed and the site rebuilds on its own.<br>
<a class="gobtn" href="{REPO}/actions/workflows/journal.yml">Open the logging form ↗</a><br>
The form runs under your GitHub sign-in: <b>only the repo's author can write here.</b>
Everyone else can read — and <a href="record.html">verify</a> — every entry.</div></div>

<div class="method"><div class="mhead"><span class="mnum">2</span>
<span class="mtitle">By talking to Claude — the MCP tools</span></div>
<div class="mbody">If the monitor's MCP server is wired into a Claude app, plain requests
write the same journal: <code>log a prediction for NVDA Q2</code> ·
<code>score my Meta prediction — wrong; actual was …; lesson …</code> ·
<code>set hyper.meta_commitments to confirm</code>. Commit and push after, so the site
sees it — the site renders committed state only.</div></div>

<div class="method"><div class="mhead"><span class="mnum">3</span>
<span class="mtitle">The raw way — edit the file</span></div>
<div class="mbody">Every entry is one JSON line in <code>journal.jsonl</code>; states live in
<code>tripwires.json</code>. Append, commit, push. No magic — which is the point: nothing
about this record depends on any one tool surviving.</div></div>

<h2>The form's fields</h2>
{fields}

<h2>Tripwire ids — for set-state</h2>
<div class="secnote">Only these hand-read filing tripwires accept a state. The six FRED
dials set themselves.</div>
{idrefs}
<footer>Entries render on the <a href="record.html">record</a> and the
<a href="index.html">dials page</a> after the next build. Research tooling only —
not investment advice.</footer>"""
    return page("Log an entry — The Useful Life of a Bubble", "log", body)


# ----------------------------------------------------------------------- start
def render_start() -> str:
    body = f"""<div class="eyebrow">The five-minute guide</div>
<div class="masthead">Start <em>here</em></div>
<div class="standfirst">What this site is, how to read it, and what it will never
tell you — written for someone new to credit, including the someone who arrived
wondering whether to short AI data-center stocks.</div>
<div class="rule"></div>

<div class="startbody">
<h2>The claim being tested</h2>
<p>A 72-page report dated 25 July 2026 — <a href="thesis.html" style="color:var(--gold)">read
its own words here</a> — argues the AI buildout is <b>two different trades that the market is
pricing as one</b>. The hyperscalers (Microsoft, Alphabet, Amazon, Meta) fund enormous
data-center spending out of enormous, audited cash flows. The periphery (Oracle, CoreWeave,
private-credit vehicles, special-purpose entities) is doing something structurally different:
financing assets that last a decade with money that comes due in about four years, borrowed
against order backlogs rather than revenue, with hundreds of billions in signed obligations
sitting off balance sheet. The claim is not that AI fails. It is that if stress comes, it
shows up <b>at the periphery's financing vehicles first</b> — not at the giants — and this
site watches for exactly that separation.</p>

<h2>How the site works</h2>
<p>The report was frozen on 25 July 2026. From that day forward it is either right or wrong,
and this monitor keeps the score in public. Six <b>credit dials</b> are fetched from FRED
every weekday; twenty-three <b>filing tripwires</b> are read by a human on event days; a
<b>dated calendar</b> lists the moments information must surface; the <b>record</b> holds
predictions made before events and scored after. Every number is fetched, never recalled
from memory; every judgment is a git commit with a timestamp nobody can quietly rewrite.</p>
<p>Each dial runs between two rails. The <span class="railword-c">coral rail</span> is
<b>confirm</b> — cross it and the evidence says the thesis is playing out. The
<span class="railword-r">blue rail</span> is <b>refute</b> — cross it and the evidence says
the thesis is wrong. The report's own house rule, Rule 10.7, is to read the refutation
side <i>first</i>: if a refuting condition is met and you catch yourself reaching for a
reason it doesn't count, the thesis has stopped being analysis and become a belief.</p>

<h2>What would prove the thesis wrong</h2>
<p>This is not a doom ticker; the wrong-way rails are watched just as hard. Concretely:
investment-grade spreads grinding tighter through their refute rail, CoreWeave reaching
next spring without touching an equity cure while growing revenue into its backlog, Oracle
converting its contracted future revenue at a healthy pace, useful-life assumptions holding
at six years or shortening. If those print, the site will say so with the same volume —
that is what the blue stamp and the <a href="record.html" style="color:var(--gold)">scored
record</a> are for.</p>

<h2>If you came here thinking about shorting</h2>
<div class="callout"><b>This site will not tell you what to trade, when, or how much —
in either direction.</b> Not because the answer is a secret, but because the honest
answer is uncomfortable: being right about a credit thesis and making money from it are
different skills, separated by financing costs, timing, and the long stretch where the
market disagrees with you.</div>
<p>The arithmetic of betting against things is unforgiving in ways that have nothing to do
with being wrong. Short positions pay borrow fees while you wait and face unlimited loss if
the market rallies; put options bleed value every day the separation doesn't arrive; a
margin call can force you out at the worst moment of a position that would eventually have
been right. Professionals who run these trades hedge them, ladder them, and size them so no
single month can end them — infrastructure a novice does not have. The old adage covers it:
markets can stay irrational longer than you can stay solvent.</p>
<p>What a newcomer can actually take from this site is the part professionals consider the
hard part: <b>the discipline</b>. Read the filings the calendar points at. Predict in
public before the print, score yourself honestly after, and keep the misses on the wall.
Learn the vocabulary in the <a href="glossary.html" style="color:var(--gold)">glossary</a>
until the footnotes read like sentences. That record — timestamped, unedited,
verifiable — is the cheapest tuition credit analysis offers, and it is worth more than a
position sized by conviction you have not yet earned.</p>

<h2>Follow along</h2>
<p>The dials update every weekday around 5:30pm Eastern. Nothing here asks for attention —
quiet days look quiet by design, and a crossing announces itself. To get the same push the
author gets, watch the <a href="{REPO}" style="color:var(--gold)">repository</a> on GitHub
(Watch → All activity): alerts arrive as issues the moment a rail is crossed or the monitor
itself breaks. Everything on this site — code, data, history, journal — is public in that
repository, and the <a href="record.html" style="color:var(--gold)">record</a> is scored
whether it flatters the thesis or not.</p>

<p style="color:var(--mut);font-size:13px;margin-top:24px">The author holds no positions in
any company named here; the record is the entire trade. Nothing on this site is investment
advice — it is one thesis, monitored honestly, in public.</p>
</div>
<footer><b>Rule 10.7:</b> read the refutation column first — it applies to this guide too.
Research tooling only — not investment advice.</footer>"""
    return page("Start here — The Useful Life of a Bubble", "start", body)


# ---------------------------------------------------------------------- thesis
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
    body = f"""<div class="eyebrow">The document · 25 July 2026</div>
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
Rule 10.7. The stage taxonomy is the monitor's construction, not the report's.
New to the vocabulary? The <a href="start.html" style="color:var(--gold)">guide</a> and
<a href="glossary.html" style="color:var(--gold)">glossary</a> translate every term.</p>
</div>
<footer>Research tooling only — not investment advice.</footer>"""
    return page("The Useful Life of a Bubble — thesis", "thesis", body)


# -------------------------------------------------------------------- glossary
def render_glossary() -> str:
    intro = "".join(f'<h3>{esc(h)}</h3><p>{esc(b)}</p>' for h, b in INTRO)
    sections = []
    for cat, entries in GLOSSARY.items():
        ents = "".join(
            f'<div class="gent"><div class="gterm">{esc(t)}</div>'
            f'<div class="gdef">{esc(d)}</div></div>'
            for t, d in entries)
        sections.append(f'<div class="gcat"><h2>{esc(cat)} · {len(entries)}</h2>{ents}</div>')
    total = sum(len(v) for v in GLOSSARY.values())
    filter_js = ("const q=document.getElementById('gq');"
                 "q.addEventListener('input',()=>{const s=q.value.toLowerCase();"
                 "document.querySelectorAll('.gent').forEach(e=>{e.style.display="
                 "e.textContent.toLowerCase().includes(s)?'':'none'});"
                 "document.querySelectorAll('.gcat').forEach(c=>{c.style.display="
                 "[...c.querySelectorAll('.gent')].some(e=>e.style.display!=='none')?'':'none'});});")
    body = f"""<div class="eyebrow">Field guide · {total} terms</div>
<div class="masthead">Glossary</div>
<div class="rule"></div>
<div class="gintro">{intro}</div>
<input class="gfilter" id="gq" type="search" placeholder="Filter terms — try: cure, OAS, useful life, RPO…" autocomplete="off">
{"".join(sections)}
<footer>Every definition is anchored to the report's own figures (25 Jul 2026). Terms are defined
by use — the way the vocabulary actually sticks. Research tooling only — not investment advice.</footer>"""
    return page("Glossary — The Useful Life of a Bubble", "glossary", body, filter_js)


def main() -> None:
    sample = "--sample" in sys.argv
    if not sample and not FRED_KEY:
        print("No FRED_API_KEY — building in gap mode (cards show [G]); use --sample for the UI preview.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(sample))
    (ROOT / "docs" / "thesis.html").write_text(render_thesis())
    (ROOT / "docs" / "glossary.html").write_text(render_glossary())
    (ROOT / "docs" / "record.html").write_text(render_record())
    (ROOT / "docs" / "log.html").write_text(render_log())
    (ROOT / "docs" / "start.html").write_text(render_start())
    print(f"Wrote docs/: index, thesis, glossary, record, log, start "
          f"({'sample preview' if sample else 'live'})")


if __name__ == "__main__":
    main()
