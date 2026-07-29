"""selftest.py — offline regression suite. Every test encodes a confirmed
red-team finding (F-numbers reference the review register in BACKLOG.md).
No network; safe to run anywhere; CI runs it before anything else."""
import json
import shutil
import tempfile
from pathlib import Path

import server
import check
import build_dashboard as bd

PASS = 0


def ok(name):
    global PASS
    PASS += 1
    print(f"  pass  {name}")


# ---------- F1/F2: evaluate() is windowed, strict, and shared ----------
chk10 = {"confirm_gt": 4.5, "refute_lt": 2.5, "sessions": 10}
status, _ = server.evaluate(chk10, [4.8] + [3.0] * 9)
assert status == "quiet", "single spike must NOT confirm a 10-session rule (F1)"
ok("F1: one-print spike stays quiet under a session rule")

status, _ = server.evaluate(chk10, [4.6] * 10)
assert status == "CONFIRM"
ok("F1: full-window breach confirms")

try:
    server.evaluate(chk10, [4.6] * 7)
    raise SystemExit("FAIL F2: short window silently evaluated")
except RuntimeError as e:
    assert "insufficient window" in str(e)
ok("F2: short window is an explicit gap, never a shrunken rule")

status, _ = server.evaluate({"confirm_gt": 4.5, "refute_lt": 2.5}, [4.5])
assert status == "quiet", "boundary equality must be quiet (strict >, per report wording)"
ok("boundary: value == threshold is quiet")

# ---------- F15: spread misalignment message ----------
_orig_fred = server.fred_latest
def _disjoint(series, n=12):
    if series == "BAMLH0A3HYC":
        return [(f"2026-06-{d:02d}", 9.9) for d in range(1, 13)]
    return [(f"2026-07-{d:02d}", 2.8) for d in range(1, 13)]
server.fred_latest = _disjoint
assert server.spread_window("BAMLH0A3HYC", "BAMLH0A0HYM2", 15) == []
server.fred_latest = _orig_fred
ok("F15: disjoint spread legs yield an empty (explicit) window")

# ---------- F3: history v2 — obs-date dedupe, GAP rows, same-day second obs ----------
tmp = Path(tempfile.mkdtemp())
_orig_hist = check.HISTORY
check.HISTORY = tmp / "history.csv"
rows1 = [{"id": "credit.ccc_oas", "date": "2026-07-27", "latest": 9.91, "status": "quiet"},
         {"id": "credit.hy_oas", "status": "GAP: timeout"}]
assert check.append_history(rows1) is True
assert check.append_history(rows1) is True, "GAP rows must append every run (visible outages)"
rows2 = [{"id": "credit.ccc_oas", "date": "2026-07-28", "latest": 9.95, "status": "quiet"}]
assert check.append_history(rows2) is True, "a NEW observation the same day must write (F3)"
rows_dup = [{"id": "credit.ccc_oas", "date": "2026-07-28", "latest": 9.95, "status": "quiet"}]
assert check.append_history(rows_dup) is False, "same (id, obs_date) must dedupe"
lines = check.HISTORY.read_text().splitlines()
assert lines[0] == "run_date,obs_date,id,value,status", "v2 header"
assert sum(1 for ln in lines if ",GAP" in ln) == 2
check.HISTORY = _orig_hist
ok("F3: v2 schema — per-(id,obs) dedupe, same-day second obs writes, GAPs recorded")

# ---------- F5a: overlay fires on preponderance despite a stray confirm ----------
def rows(**over):
    base = [dict(id=i, status="quiet", prox=p) for i, p in [
        ("credit.hy_oas", .13), ("credit.ccc_oas", .31), ("credit.dispersion", .38),
        ("credit.bbb_oas", .11), ("credit.ig_oas", .07), ("credit.ust10y", .47)]]
    for r in base:
        r.update(over.get(r["id"], {}))
    return base

# put refute states on manual key tripwires via a temp tripwires copy
_orig_tw_s, _orig_tw_b = server.TRIPWIRES_FILE, bd.TRIPWIRES_FILE
tw_tmp = tmp / "tripwires.json"
tw = json.loads(Path("tripwires.json").read_text())
for t in tw["tripwires"]:
    if t["id"] in ("crwv.backlog_ratio", "hyper.capex_ocf"):
        t["state"] = "refute"
tw_tmp.write_text(json.dumps(tw))
server.TRIPWIRES_FILE = tw_tmp
a = server.assess_stage(rows(**{
    "credit.ccc_oas": {"status": "REFUTE"}, "credit.bbb_oas": {"status": "REFUTE"},
    "credit.ig_oas": {"status": "REFUTE"},
    "credit.ust10y": {"status": "CONFIRM", "prox": 1.0}}))
assert a["refute_overlay"] is not None, "F5a: one stray confirm must not silence the overlay"
assert a["floor"] == 0, "overlay must drop the baseline floor"
ok("F5a: overlay fires on preponderance; floor yields")

# ---------- F5b: expired prior -> stage 0 reachable; terminal state exists ----------
tw2 = json.loads(Path("tripwires.json").read_text())
tw2["_meta"]["baseline_review_by"] = "2020-01-01"
tw_tmp.write_text(json.dumps(tw2))
a = server.assess_stage(rows())
assert a["baseline_expired"] and a["stage"] == 0, "expired prior must let Stage 0 exist"
tw3 = json.loads(Path("tripwires.json").read_text())
tw3["_meta"]["thesis_status"] = "REFUTED"
tw_tmp.write_text(json.dumps(tw3))
a = server.assess_stage(rows())
assert a["terminal"] and "REFUTED" in a["name"], "engine must be able to display thesis death"
ok("F5b: prior expires to 0; terminal thesis state renders")

# ---------- F5c: gap-aware assessment ----------
tw_tmp.write_text(Path("tripwires.json").read_text())  # clean meta
gap_rows = [dict(id=i, status="GAP: dead") for i, _ in
            [("credit.hy_oas", 0), ("credit.ccc_oas", 0), ("credit.dispersion", 0),
             ("credit.bbb_oas", 0), ("credit.ig_oas", 0), ("credit.ust10y", 0)]]
a = server.assess_stage(gap_rows)
assert a["gaps"] == 6 and a["evidence_note"] and "6 dark" in a["evidence_note"]
ok("F5c: all-dark assessment discloses its own blindness")
server.TRIPWIRES_FILE = _orig_tw_s

# ---------- F13: state fields are escaped; note renders ----------
tw4 = json.loads(Path("tripwires.json").read_text())
EVIL = '"><img src=x onerror=alert(1)>'
for t in tw4["tripwires"]:
    if t["id"] == "supply.vertiv_disclosure":
        t["state"], t["state_as_of"], t["state_note"] = EVIL, "2026-07-28", EVIL
tw_tmp.write_text(json.dumps(tw4))
server.TRIPWIRES_FILE = tw_tmp
bd.TRIPWIRES_FILE = tw_tmp
html_out = bd.render(True)
assert EVIL not in html_out, "F13: raw payload must never reach HTML"
assert "&quot;&gt;&lt;img" in html_out, "escaped form should be present (note renders escaped)"
server.TRIPWIRES_FILE = _orig_tw_s
bd.TRIPWIRES_FILE = _orig_tw_b
ok("F13: hostile state/state_note is escaped, note is rendered")

# ---------- F7: corrupt journal line cannot kill the build ----------
_orig_j_s, _orig_j_b = server.JOURNAL_FILE, bd.JOURNAL_FILE
jtmp = tmp / "journal.jsonl"
jtmp.write_text('{"kind":"prediction","event":"x","prediction":"y","ts":"t"}\n{"kind":"score","ev')
server.JOURNAL_FILE = jtmp
bd.JOURNAL_FILE = jtmp
html_out = bd.render(True)
assert "unreadable journal line" in html_out
server.JOURNAL_FILE = _orig_j_s
bd.JOURNAL_FILE = _orig_j_b
ok("F7: truncated journal line degrades to a visible note, build survives")

# ---------- sample-mode honesty + new UI probes ----------
html_out = bd.render(True)
assert 'class="card confirm' not in html_out and 'class="card refute' not in html_out, \
    "sample data must never fabricate a crossing"
assert "Reveal last build's assessment" in html_out, "F19 button relabel"
assert "monitor's construction, not the" in html_out, "F19 attribution"
assert "Nearest threshold" in html_out, "F11 symmetric pulse"
assert "month-verified" in html_out, "F9 honest date precision"
ok("sample build: no fabricated alerts; F19/F11/F9 surfaces present")


# ---------- glossary & legibility surfaces ----------
gg = bd.render_glossary()
n_terms = gg.count('class="gent"')
assert n_terms >= 75, f"glossary too thin: {n_terms} terms"
assert 'id="gq"' in gg and "addEventListener" in gg, "glossary filter missing"
assert "Equity cure" in gg and "4.61" in gg and "3.58x" in gg, "key anchored entries missing"
html_out = bd.render(True)
assert 'glossary.html' in html_out, "nav must link the glossary"
assert 'class="tick"' in html_out and "CCC\u2212HY" in html_out, "dial ticker codes missing"
assert "grid-template-columns:1fr}" in html_out, "mobile single-column rule missing"
ok(f"glossary renders ({n_terms} terms) + filter; ticker codes + mobile layout present")

# ---------- 29 Jul legibility pass: plain layer, rail grammar, neutral chips ----------
html_out = bd.render(True)
for pid, line in bd.PLAIN.items():
    assert line[:40] in html_out, f"plain one-liner missing for {pid}"
assert 'class="nowline"' in html_out and "Right now:" in html_out, "plain state line missing"
assert "thesis-wrong rail" in html_out, "rail grammar (plain legend/reading) missing"
assert 'class="delta up"' not in html_out and 'class="delta dn"' not in html_out, \
    "drift chips must not wear alarm colors — status colors are reserved for status"
for pg in ("start.html", "record.html", "log.html"):
    assert pg in html_out, f"nav missing {pg}"
assert 'data-tip=' in html_out, "inline glossary tips missing from index"
assert html_out.count('<div class="cname"><span class="dfn"') == 6, \
    "every dial card's name must carry a glossary tip"
ok("legibility: plain layer + rail grammar + neutral drift chips + full nav")

# ---------- inline tips: hostile glossary definition is escaped ----------
_orig_gloss = bd.GLOSSARY
bd.GLOSSARY = {"Cat": [("OAS", EVIL)]}
tip_html = bd.render(True)
bd.GLOSSARY = _orig_gloss
assert EVIL not in tip_html, "raw glossary payload must never reach a data-tip attribute"
assert 'data-tip=' in tip_html, "tip span should still render, escaped"
ok("tips: hostile definition escaped inside data-tip")

# ---------- record page: pairing, tally, escaping, provenance, tolerance ----------
jr = tmp / "journal_record.jsonl"
jr.write_text(
    '{"kind":"prediction","event":"Meta Q2 2026","prediction":"commitments ~$310bn",'
    '"reasoning":"because velocity","ts":"2026-07-28T21:24:54+00:00"}\n'
    '{"kind":"prediction","event":"' + EVIL.replace('"', '\\"') + '","prediction":"x",'
    '"ts":"2026-07-28T22:00:00+00:00"}\n'
    '{"kind":"score","event":"Meta Q2 2026","actual":"printed $301bn","verdict":"wrong",'
    '"lesson":"velocity persists","ts":"2026-07-30T01:00:00+00:00"}\n'
    '{"kind":"score","ev')
_orig_j_rec = bd.JOURNAL_FILE
bd.JOURNAL_FILE = jr
rec = bd.render_record()
bd.JOURNAL_FILE = _orig_j_rec
assert '<div class="pk">Predictions</div><div class="tnum">2</div>' in rec, "tally: 2 predictions"
assert '<div class="pk">Scored</div><div class="tnum">1</div>' in rec, "tally: 1 scored"
assert "v-wrong" in rec and "printed $301bn" in rec and "velocity persists" in rec, \
    "scored pair must show verdict, actual, lesson"
assert "awaiting result" in rec, "unscored prediction must show as awaiting"
assert EVIL not in rec, "hostile event name must be escaped on the record page"
assert "commits/main/journal.jsonl" in rec, "record must link its git provenance"
assert "unreadable journal line" in rec, "truncated line must degrade visibly (F7 parity)"
ok("record: pairs scores to predictions, honest tally, escaped, provenanced")

# ---------- log page: form link, field rules, id reference, authorship ----------
lg = bd.render_log()
assert "actions/workflows/journal.yml" in lg, "log must deep-link the dispatch form"
assert "hyper.meta_commitments" in lg and 'class="twid"' in lg, "tripwire id reference missing"
assert "only the repo's author can write" in lg, "authorship honesty line missing"
assert "clear" in lg and "mixed" in lg, "field rules must mirror journal.yml validation"
ok("log: dispatch form linked, fields documented, ids listed, authorship stated")

# ---------- start page: orientation with boundaries intact ----------
st = bd.render_start()
assert "not investment advice" in st, "start page must carry the not-advice line"
assert "will not tell you what to trade" in st, "the boundary must be stated as design"
assert "Rule 10.7" in st and "refutation" in st, "refute-first must be taught"
assert "stay solvent" in st, "the solvency adage belongs in the shorting section"
assert 'record.html' in st and 'glossary.html' in st, "start must route to record + glossary"
ok("start: orientation present, boundaries stated, refute-first taught")

# ---------- stage panel teaches itself: examples, floor translation, flip tips ----------
a_probe = server.assess_stage(rows())
for lbl, _ok, _lvl in a_probe["rules"]:
    assert lbl in bd.STAGE_EXAMPLES, f"stage rule lacks an example (relabeled?): {lbl}"
html_out = bd.render(True)
assert "In plain terms" in html_out, "computed/floor/stamp must be translated to plain language"
assert "What the stages mean" in html_out and "Priced as one" in html_out, \
    "stage-names tip must render, built from server.STAGE_NAMES"
assert "equity cure after the 28 Oct window closes" in html_out, \
    "rule examples must reach the rendered panel"
assert "tipPlace" in html_out and "--tipx" in html_out and "flipy" in html_out, \
    "tips must be JS-placed: clamped inside the viewport, flipping above when low"
ok("stage panel: every rule carries an example; floor translated; tips flip to fit")

# ---------- gauge: hard rails, tipped labels, tips wrap inside their box ----------
html_out = bd.render(True)
assert "white-space:normal" in html_out, \
    "tip box must force wrapping — nowrap ancestors (chips, gauge labels) leak into ::after"
assert ".gtrack::before" in html_out and ".gtrack::after" in html_out, \
    "rails must render as hard end caps, not a gradient continuum"
assert html_out.count("thesis-wrong side") >= 6, "every gauge needs a tipped refute label"
assert html_out.count("thesis-right side") >= 6, "every gauge needs a tipped confirm label"
ok("gauge: hard rail caps, refute/confirm/delta tips on all six dials, tips wrap")

shutil.rmtree(tmp, ignore_errors=True)
print(f"\nALL {PASS} REGRESSION TESTS PASS")
