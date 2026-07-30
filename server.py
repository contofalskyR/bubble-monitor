"""
bubble-monitor — MCP server for tracking "The Useful Life of a Bubble" (Section 10).

Division of labor, by design:
  AUTOMATED : retrieval (FRED, EDGAR), threshold checks, calendar, journaling.
  HUMAN     : reading the filing passage, making the call, scoring it.

Every number this server returns is fetched, never recalled. Anything it cannot
fetch is labelled a gap — the report's [V]/[G] discipline, enforced in code.

Post red-team hardening (see BACKLOG.md for the findings register):
  - evaluate() is the SINGLE source of truth for status + proximity; the cron
    path and the dashboard both call it, so they cannot disagree (F1).
  - fred_window() guarantees a full session window or an explicit gap (F2).
  - assess_stage() can lose: preponderance-based refute overlay, a defeasible
    expiring baseline prior, gap-awareness, and a human-declared terminal
    thesis_status (F5a-c).
  - The MCP SDK import is optional; check.py and build_dashboard.py run even if
    the SDK is absent or breaks in a future major version (F8).

Run standalone:        python server.py          (stdio transport)
Run the daily check:   python check.py           (same core functions, cron entry)
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import requests

# --- MCP SDK import shim: 2.x, then 1.x, then a no-op so cron never dies (F8) ---
try:  # SDK >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:
    try:  # SDK 1.x
        from mcp.server.fastmcp import FastMCP as _Server
    except ImportError:
        _Server = None  # core functions still work; only chat-server mode is off

ROOT = Path(__file__).resolve().parent
TRIPWIRES_FILE = ROOT / "tripwires.json"
CALENDAR_FILE = ROOT / "calendar.json"
JOURNAL_FILE = ROOT / "journal.jsonl"

FRED_KEY = os.environ.get("FRED_API_KEY", "")
_UA_PLACEHOLDER = "bubble-monitor (set EDGAR_UA env var)"
EDGAR_UA = os.environ.get("EDGAR_UA", _UA_PLACEHOLDER)
HEADERS = {"User-Agent": EDGAR_UA}

# CIKs from the report's Section 13.1 (10-digit zero-padded, as EDGAR requires)
WATCHLIST = {
    "meta": "0001326801",
    "microsoft": "0000789019",
    "alphabet": "0001652044",
    "amazon": "0001018724",
    "oracle": "0001341439",
    "nvidia": "0001045810",
    "coreweave": "0001769628",
    "amd": "0000002488",
    "broadcom": "0001730168",
    "intel": "0000050863",
    "ge vernova": "0001996810",
    "vertiv": "0001674101",
}

if _Server is not None:
    mcp = _Server(
        "bubble-monitor",
        instructions=(
            "Tools for monitoring the AI-infrastructure credit thesis. Fetch, check "
            "thresholds, and journal — but filings must be read and predictions "
            "scored by the human. Never state a figure that was not fetched."
        ),
    )
else:
    class _NoOpServer:
        """SDK absent/broken: decorators become identity; run() explains itself."""

        def tool(self, *a, **k):
            return lambda f: f

        def run(self, *a, **k):
            raise SystemExit(
                "MCP SDK not importable — chat-server mode unavailable. "
                "check.py and build_dashboard.py are unaffected. "
                "Fix: pip install 'mcp>=1.2,<3'."
            )

    mcp = _NoOpServer()

# ============================ core (plain) functions ========================
# Kept undecorated-callable so check.py, build_dashboard.py, selftest.py can
# import them directly, with or without the MCP SDK installed.


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _require_ua() -> None:
    """SEC fair-access guidance expects an identifying UA with contact info (F14)."""
    if EDGAR_UA == _UA_PLACEHOLDER or "@" not in EDGAR_UA:
        raise RuntimeError(
            "EDGAR_UA is not set to an identifying string with contact info. "
            'Export EDGAR_UA="bubble-monitor your-email@university.edu" first — '
            "SEC throttles or blocks anonymous automated clients."
        )


def fred_latest(series_id: str, n: int = 12) -> list[tuple[str, float]]:
    """Most recent n VALID observations, newest first. Note: FRED '.' placeholders
    are filtered AFTER the limit, so callers needing a guaranteed window size must
    use fred_window()."""
    if not FRED_KEY:
        raise RuntimeError(
            "FRED_API_KEY not set. Get a free key at fred.stlouisfed.org "
            "(My Account -> API Keys) and export FRED_API_KEY=..."
        )
    r = requests.get(
        "https://api.stlouisfed.org/fred/series/observations",
        params={
            "series_id": series_id,
            "api_key": FRED_KEY,
            "file_type": "json",
            "sort_order": "desc",
            "limit": n,
        },
        timeout=30,
    )
    r.raise_for_status()
    obs = [o for o in r.json()["observations"] if o["value"] not in (".", "")]
    return [(o["date"], float(o["value"])) for o in obs]


def fred_window(series_id: str, sessions: int, buffer: int = 8) -> list[tuple[str, float]]:
    """Exactly `sessions` valid observations, newest first — or an explicit gap.
    Never silently evaluates a declared 10-session rule over fewer prints (F2)."""
    sessions = max(sessions, 1)
    obs = fred_latest(series_id, sessions + buffer)
    if len(obs) < sessions:
        raise RuntimeError(f"only {len(obs)}/{sessions} sessions available")
    return obs[:sessions]


def spread_window(series_a: str, series_b: str, n: int = 15) -> list[tuple[str, float]]:
    """Newest-first (date, a-b) pairs over common observation dates. Shared by the
    cron and the dashboard so the two paths cannot gap-disagree (F15)."""
    a = dict(fred_latest(series_a, n + 10))
    b = dict(fred_latest(series_b, n + 10))
    common = sorted(set(a) & set(b), reverse=True)[:n]
    return [(d, round(a[d] - b[d], 2)) for d in common]


def evaluate(chk: dict, window_newest_first: list[float]) -> tuple[str, float]:
    """THE single source of truth for status + proximity (F1). `window` must be
    newest-first; the declared session count is enforced, never approximated.
    'Sustained' (refute) is operationalized as the same session window — a
    documented interpretation, recorded in tripwires.json _meta."""
    n = max(chk.get("sessions", 1), 1)
    if len(window_newest_first) < n:
        raise RuntimeError(f"insufficient window: {len(window_newest_first)}/{n} sessions")
    w = window_newest_first[:n]
    confirm = all(v > chk["confirm_gt"] for v in w)
    refute = all(v < chk["refute_lt"] for v in w)
    status = "CONFIRM" if confirm else "REFUTE" if refute else "quiet"
    span = (chk["confirm_gt"] - chk["refute_lt"]) or 1
    prox = max(0.0, min(1.0, (w[0] - chk["refute_lt"]) / span))
    return status, round(prox, 3)


def run_credit_checks() -> tuple[list[dict], list[str]]:
    """Execute every auto-checkable (FRED) tripwire via evaluate(). Returns (rows, alerts)."""
    tw = _load(TRIPWIRES_FILE)["tripwires"]
    rows, alerts = [], []
    for t in tw:
        chk = t.get("check", {})
        kind = chk.get("type")
        if kind not in ("fred", "fred_spread"):
            continue
        sess = max(chk.get("sessions", 1), 1)
        try:
            if kind == "fred":
                obs = fred_window(chk["series"], sess)
            else:
                obs = spread_window(chk["series_a"], chk["series_b"], max(15, sess))
                if not obs:
                    raise RuntimeError("no common observation date in last 15 sessions")
                if len(obs) < sess:
                    raise RuntimeError(f"only {len(obs)}/{sess} common sessions available")
            latest_date, latest = obs[0]
            status, prox = evaluate(chk, [v for _, v in obs])
            rows.append(
                {
                    "id": t["id"],
                    "name": t["name"],
                    "latest": latest,
                    "date": latest_date,
                    "confirms": t["confirms"],
                    "refutes": t["refutes"],
                    "status": status,
                    "prox": prox,
                    "sessions": sess,
                }
            )
            if status != "quiet":
                basis = f"all of the last {sess} sessions" if sess > 1 else "latest print"
                alerts.append(
                    f"{t['name']}: {latest} on {latest_date} -> {status} "
                    f"({basis}; threshold: {t['confirms'] if status == 'CONFIRM' else t['refutes']})"
                )
        except Exception as exc:  # a failed fetch is a gap, never a guess
            rows.append({"id": t["id"], "name": t["name"], "status": f"GAP: {exc}"})
    return rows, alerts


def edgar_fulltext(
    query: str, forms: str = "", company: str = "", start: str = "", end: str = ""
) -> dict:
    """EDGAR full-text search (efts.sec.gov) — the report's spine tool."""
    _require_ua()
    params: dict = {"q": query}
    if forms:
        params["forms"] = forms
    if company:
        cik = WATCHLIST.get(company.lower(), company)
        params["ciks"] = str(cik).zfill(10)
    if start:
        params["startdt"] = start
    if end:
        params["enddt"] = end
    r = requests.get(
        "https://efts.sec.gov/LATEST/search-index",
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def edgar_recent(company: str, form_type: str = "", n: int = 10) -> list[dict]:
    """Most recent filings for a watchlist company via data.sec.gov submissions."""
    _require_ua()
    cik = WATCHLIST.get(company.lower())
    if not cik:
        raise ValueError(f"Unknown company '{company}'. Watchlist: {sorted(WATCHLIST)}")
    r = requests.get(
        f"https://data.sec.gov/submissions/CIK{cik}.json", headers=HEADERS, timeout=30
    )
    r.raise_for_status()
    recent = r.json()["filings"]["recent"]
    out = []
    for form, fdate, accession, doc in zip(
        recent["form"], recent["filingDate"], recent["accessionNumber"], recent["primaryDocument"]
    ):
        if form_type and form != form_type:
            continue
        acc = accession.replace("-", "")
        out.append(
            {
                "form": form,
                "filed": fdate,
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{doc}",
            }
        )
        if len(out) >= n:
            break
    return out


VEHICLE_IDS = {"crwv.equity_cures", "crwv.liquidity", "orcl.uncommenced_leases"}
KEY_REFUTE_IDS = {"credit.ccc_oas", "crwv.backlog_ratio", "hyper.capex_ocf", "crwv.equity_cures"}
STAGE_NAMES = {0: "Priced as one", 1: "Repricing begins", 2: "Pressure builds",
               3: "Separation at the vehicle level", 4: "Resolution — broad repricing"}


def assess_stage(auto_rows=None, gaps: int | None = None) -> dict:
    """Transparent stage engine. Declared rules over tracked evidence; the
    baseline prior, gap count, and every rule evaluation are returned, never
    hidden. Capable of losing (F5a-c): the refute overlay fires on preponderance;
    the baseline floor yields when the overlay fires or the prior expires
    unrenewed; a human-declared thesis_status is terminal."""
    tw = _load(TRIPWIRES_FILE)
    meta = tw["_meta"]
    baseline = meta.get("baseline_stage", 0)
    basenote = meta.get("baseline_note", "")
    manual = {t["id"]: t for t in tw["tripwires"] if t["check"]["type"] == "manual"}
    if auto_rows is None:
        auto_rows, _ = run_credit_checks()
    gap_rows = [r for r in auto_rows if str(r["status"]).startswith("GAP")]
    if gaps is None:
        gaps = len(gap_rows)
    auto = {r["id"]: r for r in auto_rows if not str(r["status"]).startswith("GAP")}

    confirms = sorted([i for i, r in auto.items() if r["status"] == "CONFIRM"] +
                      [i for i, t in manual.items() if t.get("state") == "confirm"])
    refutes = sorted([i for i, r in auto.items() if r["status"] == "REFUTE"] +
                     [i for i, t in manual.items() if t.get("state") == "refute"])
    hot = sorted([i for i, r in auto.items() if r.get("prox", 0) >= 0.85 and r["status"] == "quiet"])
    disp_prox = auto.get("credit.dispersion", {}).get("prox", 0)
    periph = [i for i in confirms if i.split(".")[0] in ("orcl", "crwv", "nvda")]
    vehicle = [i for i in confirms if i in VEHICLE_IDS]

    rules = [
        ("HY index crossed 4.50 (systemic repricing)", auto.get("credit.hy_oas", {}).get("status") == "CONFIRM", 4),
        ("2+ vehicle-level binary events confirmed", len(vehicle) >= 2, 4),
        ("A vehicle-level binary event confirmed (cures / liquidity / lease cancellation)", len(vehicle) >= 1, 3),
        ("3+ periphery tripwires confirmed", len(periph) >= 3, 3),
        ("Any credit dial crossed its confirm threshold", any(i.startswith("credit.") for i in confirms), 2),
        ("3+ confirms across all categories", len(confirms) >= 3, 2),
        ("2+ dials at 85%+ of the way to confirm", len(hot) >= 2, 2),
        ("First confirm anywhere", len(confirms) >= 1, 1),
        ("Dispersion 50%+ of the way to confirm", disp_prox >= 0.5, 1),
        ("Any dial running hot (70%+ to confirm)", any(r.get("prox", 0) >= 0.7 for r in auto.values()), 1),
    ]
    computed = max([lvl for _, ok, lvl in rules if ok], default=0)

    # refute overlay: fires on preponderance, not perfection (F5a)
    key_ref = [i for i in refutes if i in KEY_REFUTE_IDS]
    refute_overlay = None
    if len(key_ref) >= 2 and len(refutes) > len(confirms):
        refute_overlay = ("REFUTE PATH: multiple key refutation conditions met and refutes "
                          "outnumber confirms — the thesis is losing, not resting.")
    elif len(refutes) >= len(confirms) + 3:
        refute_overlay = "Refutes outnumber confirms by 3+ — weigh the bull case before the next prediction."

    # defeasible baseline (F5b): floor yields to the overlay, and expires unrenewed
    expired = meta.get("baseline_review_by", "9999-12-31") < date.today().isoformat()
    floor = 0 if (refute_overlay or expired) else baseline
    stage = max(computed, floor)

    out = {
        "stage": stage, "name": STAGE_NAMES[stage], "computed": computed,
        "baseline": baseline, "baseline_note": basenote, "baseline_expired": expired,
        "floor": floor, "rules": rules, "confirms": confirms, "refutes": refutes,
        "hot": hot, "refute_overlay": refute_overlay, "gaps": gaps, "terminal": False,
        "evidence_note": (f"computed from {len(auto)} of {len(auto) + gaps} dials — {gaps} dark"
                          if gaps else None),
        "next_up": ("Stage " + str(min(stage + 1, 4)) + " requires: " +
                    "; ".join(lbl for lbl, ok, lvl in rules if lvl == min(stage + 1, 4) and not ok)
                    if stage < 4 else "Terminal stage."),
        "refute_path": "Refute path (2 of): CCC OAS < 8.50; CRWV backlog ratio falls via growth; big-four capex/OCF < 85%; no cure used through Q1 2027.",
    }

    # human-declared terminal state (F5b): engine displays it, never invents it
    status = meta.get("thesis_status", "OPEN")
    if status in ("REFUTED", "CONFIRMED", "REVISED"):
        out.update({"stage": None, "name": f"THESIS {status} — see journal for the closing memo",
                    "terminal": True})
    return out


def journal_append(entry: dict) -> None:
    entry["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with JOURNAL_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


PUBLISH_FILES = ("journal.jsonl", "tripwires.json")


def _autopublish(msg: str) -> str:
    """The entry is the only human act — everything downstream is machinery.

    After a journal/state write, commit and push so the site rebuilds itself.
    Stages ONLY the two record files, never anything else (private files in the
    working tree stay private). Skipped inside CI (workflows own their commits)
    or when BUBBLE_AUTOPUSH=0. Every failure degrades to a warning string — the
    write is already safe on disk, and the next successful publish carries it."""
    if os.environ.get("GITHUB_ACTIONS") or os.environ.get("BUBBLE_AUTOPUSH") == "0":
        return "Commit journal.jsonl/tripwires.json to publish — the site renders committed state only."
    def run(*args, timeout=45):
        return subprocess.run(["git", "-C", str(ROOT), *args],
                              capture_output=True, text=True, timeout=timeout)
    try:
        a = run("add", "--", *PUBLISH_FILES)
        c = run("commit", "-m", msg)
        if c.returncode != 0:
            out = (c.stdout + c.stderr).lower()
            if a.returncode == 0 and "nothing to commit" in out:
                return "Nothing new to publish (already committed)."
            return ("PUBLISH INCOMPLETE — the write is safe on disk, but the commit failed: "
                    + (c.stderr or c.stdout).strip()[:300])
        p = run("pull", "--rebase", "--autostash", "origin", "main", timeout=90)
        if p.returncode == 0:
            p = run("push", timeout=90)
        if p.returncode != 0:
            return ("PUBLISH INCOMPLETE — committed locally, but sync/push failed: "
                    + (p.stderr or p.stdout).strip()[:300]
                    + " | Your entry is safe; run 'git pull' then 'git push' whenever, "
                      "or use the phone form — either carries it up.")
        return "Published — committed and pushed. The site rebuilds itself in ~2 minutes."
    except Exception as exc:  # timeout, git missing — never lose or block the write
        return (f"PUBLISH INCOMPLETE — {exc}. Your entry is safe on disk; "
                f"it publishes with the next successful push.")


# ================================ MCP tools =================================


@mcp.tool()
def check_credit_tripwires() -> str:
    """Fetch the report's FRED spread series and score each against its Section
    10.4.1 confirm/refute thresholds. The daily pulse of the thesis."""
    rows, alerts = run_credit_checks()
    lines = ["TRIPWIRE CHECK — " + date.today().isoformat(), ""]
    for r in rows:
        if r["status"].startswith("GAP"):
            lines.append(f"  [GAP]      {r['name']}: {r['status']}")
        else:
            flag = {"quiet": "[quiet]  ", "CONFIRM": "[CONFIRM]", "REFUTE": "[REFUTE] "}[r["status"]]
            sess = f" ({r['sessions']}-session window)" if r.get("sessions", 1) > 1 else ""
            lines.append(f"  {flag} {r['name']}: {r['latest']} ({r['date']}){sess}")
    lines.append("")
    lines.append("ALERTS: " + ("; ".join(alerts) if alerts else "none — all quiet"))
    gaps = sum(1 for r in rows if str(r["status"]).startswith("GAP"))
    if gaps:
        lines.append(f"NOTE: {gaps} dial(s) dark — the absence of a number is a finding, not a pass.")
    lines.append("Manual tripwires (filings) are NOT covered here: use list_tripwires('nvidia') etc. on event days.")
    return "\n".join(lines)


@mcp.tool()
def fred_series(series_id: str, n: int = 12) -> str:
    """Raw recent observations for any FRED series (e.g. BAMLH0A3HYC = CCC OAS,
    BAMLC0A0CM = IG OAS, DGS10 = 10y Treasury)."""
    obs = fred_latest(series_id, n)
    return "\n".join(f"{d}: {v}" for d, v in obs)


@mcp.tool()
def edgar_search(query: str, forms: str = "", company: str = "", start: str = "", end: str = "") -> str:
    """Full-text search across EDGAR filings. Use double quotes inside the query
    for exact phrases (e.g. '"unlimited number of equity cures"'). Optional:
    forms='8-K', company='coreweave' (watchlist name or CIK), start/end='YYYY-MM-DD'.
    This is how the report tested presence AND absence of language — an empty
    result is itself a finding."""
    data = edgar_fulltext(query, forms, company, start, end)
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    hits = data.get("hits", {}).get("hits", [])[:10]
    lines = [f"{total} total hits for {query!r}" + (f" [{forms}]" if forms else "")]
    for h in hits:
        s = h.get("_source", {})
        names = ", ".join(s.get("display_names", [])[:1])
        lines.append(f"  {s.get('file_date','?')}  {s.get('file_type','?'):8s}  {names}")
    if total == 0:
        lines.append("  (zero hits — a negative finding; remember the report's Oracle lesson in Sec 12.3.7 before trusting it)")
    return "\n".join(lines)


@mcp.tool()
def latest_filings(company: str, form_type: str = "", n: int = 8) -> str:
    """Most recent EDGAR filings for a watchlist company, with direct document
    URLs. company: meta, microsoft, alphabet, amazon, oracle, nvidia, coreweave,
    amd, broadcom, intel, 'ge vernova', vertiv. Optional form_type: 10-Q, 10-K, 8-K."""
    rows = edgar_recent(company, form_type, n)
    if not rows:
        return f"No {form_type or 'recent'} filings found for {company}."
    return "\n".join(f"{r['filed']}  {r['form']:8s}  {r['url']}" for r in rows)


@mcp.tool()
def list_tripwires(category: str = "") -> str:
    """The report's Section 10.4 tripwires with current values and confirm/refute
    thresholds. Categories: credit, nvidia, oracle, coreweave, hyperscalers,
    supply_chain. Rule 10.7: read the refutation column first."""
    tw = _load(TRIPWIRES_FILE)["tripwires"]
    if category:
        tw = [t for t in tw if t["category"] == category.lower()]
    lines = []
    for t in tw:
        lines.append(f"[{t['category']}] {t['name']}")
        lines.append(f"    now:      {t['current']}")
        lines.append(f"    CONFIRMS: {t['confirms']}")
        lines.append(f"    REFUTES:  {t['refutes']}")
        if t.get("state"):
            lines.append(f"    STATE:    {t['state']} (as of {t.get('state_as_of','?')}) {t.get('state_note','')}")
        if t.get("notes"):
            lines.append(f"    note:     {t['notes']}")
    return "\n".join(lines) if lines else f"No tripwires in category '{category}'."


@mcp.tool()
def upcoming_events(days: int = 45) -> str:
    """Dated calendar from the report's Section 10.3, next N days — load-bearing
    dates are always shown regardless of window. Month-precision dates render as
    'Sep 2026' with an approximate countdown. On each: log_prediction BEFORE,
    score_prediction AFTER."""
    events = _load(CALENDAR_FILE)["events"]
    today = date.today()
    out = []
    for e in events:
        d = date.fromisoformat(e["date"])
        delta = (d - today).days
        if delta < 0:
            continue
        if delta > days and not e.get("load_bearing"):
            continue
        star = " *** LOAD-BEARING ***" if e.get("load_bearing") else ""
        month_only = e.get("precision") == "month"
        when = d.strftime("%b %Y") if month_only else e["date"]
        chip = f"~{delta}d" if month_only else f"+{delta}d"
        out.append(f"{when} ({chip}) [{e['tag']}]{star}\n    {e['event']}\n    watch: {e['watch']}")
    return "\n".join(out) if out else f"No calendar events in the next {days} days."


@mcp.tool()
def set_tripwire_state(tripwire_id: str, state: str, note: str = "") -> str:
    """After reading a filing on an event day, record a manual tripwire's state:
    'confirm', 'refute', 'quiet', or 'clear' (unset). Updates tripwires.json —
    commit it with a message saying WHY (your anti-goalpost-moving log)."""
    state = state.lower()
    if state not in ("confirm", "refute", "quiet", "clear"):
        return "State must be confirm, refute, quiet, or clear."
    tw = _load(TRIPWIRES_FILE)
    for t in tw["tripwires"]:
        if t["id"] == tripwire_id:
            if t["check"]["type"] != "manual":
                return f"{tripwire_id} is auto-checked; its state comes from FRED."
            if state == "clear":
                for k in ("state", "state_as_of", "state_note"):
                    t.pop(k, None)
            else:
                t["state"] = state
                t["state_as_of"] = date.today().isoformat()
                if note:
                    t["state_note"] = note
            TRIPWIRES_FILE.write_text(json.dumps(tw, indent=2) + "\n")
            cm = f"state: {tripwire_id} -> {state} [via mcp]" + (f" — {note[:80]}" if note else "")
            return f"{tripwire_id} -> {state}.\n" + _autopublish(cm)
    return f"No tripwire with id {tripwire_id!r}. Use list_tripwires() for ids."


@mcp.tool()
def assess_thesis_stage() -> str:
    """Run the declared stage rules over every tracked signal — auto dials plus
    your recorded manual states — and report the stage with full evidence, the
    gap count, the baseline prior, and the refute path (always shown). The stage
    taxonomy is this monitor's construction, not the report's."""
    a = assess_stage()
    if a["terminal"]:
        return f"{a['name']}\n(Reopen by setting _meta.thesis_status back to OPEN in tripwires.json, with a journal memo.)"
    lines = [f"STAGE {a['stage']} — {a['name']}",
             f"(computed {a['computed']}, baseline floor {a['floor']} of prior {a['baseline']}: {a['baseline_note']})"]
    if a["evidence_note"]:
        lines.append(f"!! {a['evidence_note']} — treat this assessment as partial.")
    if a["baseline_expired"]:
        lines.append("!! Baseline prior EXPIRED unrenewed — floor dropped to 0. Renew _meta.baseline_review_by with the quarterly memo, or let it stay dropped.")
    lines.append("")
    for lbl, ok, lvl in a["rules"]:
        lines.append(f"  [{'x' if ok else ' '}] S{lvl}  {lbl}")
    lines.append("")
    lines.append(f"Confirms: {', '.join(a['confirms']) or 'none'}")
    lines.append(f"Refutes:  {', '.join(a['refutes']) or 'none'}")
    if a["hot"]:
        lines.append(f"Running hot: {', '.join(a['hot'])}")
    if a["refute_overlay"]:
        lines.append("\n" + a["refute_overlay"])
    lines.append("\n" + a["next_up"])
    lines.append(a["refute_path"])
    return "\n".join(lines)


@mcp.tool()
def log_prediction(event: str, prediction: str, reasoning: str = "") -> str:
    """BEFORE an event: record your call, timestamped and append-only. This is
    the discipline that makes the track record honest — no editing after the fact."""
    journal_append({"kind": "prediction", "event": event, "prediction": prediction, "reasoning": reasoning})
    return f"Logged prediction for: {event}\n" + _autopublish(f"journal(prediction): {event} [via mcp]")


@mcp.tool()
def score_prediction(event: str, actual: str, verdict: str, lesson: str = "") -> str:
    """AFTER the event: what actually printed, your grade (right / wrong / mixed),
    and the lesson. Scoring your own misses is the entire point (Sec 10.7 rule 1)."""
    journal_append({"kind": "score", "event": event, "actual": actual, "verdict": verdict, "lesson": lesson})
    return f"Scored: {event} -> {verdict}\n" + _autopublish(f"journal(score): {event} -> {verdict} [via mcp]")


@mcp.tool()
def journal_review(n: int = 20) -> str:
    """Read back the last N journal entries — predictions and scores together."""
    if not JOURNAL_FILE.exists():
        return "Journal is empty. Log your first prediction before the next print."
    out, bad = [], 0
    for ln in JOURNAL_FILE.read_text().strip().splitlines()[-n:]:
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            bad += 1
            continue
        if e["kind"] == "prediction":
            out.append(f"{e['ts']}  PREDICT  {e['event']}: {e['prediction']}")
        else:
            out.append(f"{e['ts']}  SCORE    {e['event']}: {e['verdict']} — {e['actual']}")
    if bad:
        out.append(f"({bad} unreadable line(s) skipped — check journal.jsonl for a truncated write)")
    return "\n".join(out)


if __name__ == "__main__":
    mcp.run()  # stdio — what Claude Desktop / Claude Code connect to
