"""Daily tripwire check — cron entry point (GitHub Actions or local).

Post red-team hardening:
  - history.csv v2 (F3): run_date AND obs_date; dedupe per (id, obs_date) so a
    morning run never blocks the day's real print; GAP rows are written, so
    outages are visible IN the dataset, not holes in it.
  - ALERT carries a class (F16): TRIPWIRE vs MONITOR-BROKEN, so the push
    notification for "the instrument is blind" never reads like a market event.
  - The stage line's failures are logged, not swallowed (F23).
"""
import csv
import os
from datetime import date
from pathlib import Path

from server import FRED_KEY, run_credit_checks, assess_stage

ROOT = Path(__file__).resolve().parent
HISTORY = ROOT / "data" / "history.csv"
IN_CI = os.environ.get("GITHUB_ACTIONS") == "true"
HEADER = ["run_date", "obs_date", "id", "value", "status"]


def append_history(rows) -> bool:
    """Append readings in v2 long format. Dedupe on (id, obs_date) — a new FRED
    observation always gets a row regardless of how many runs happen today. GAP
    rows always append (one per run) so outage duration is measurable."""
    run = date.today().isoformat()
    seen: set[tuple[str, str]] = set()
    if HISTORY.exists() and HISTORY.stat().st_size > 0:
        for ln in HISTORY.read_text().splitlines()[1:]:
            p = ln.split(",")
            if len(p) >= 3:
                seen.add((p[2], p[1]))  # (id, obs_date)
    HISTORY.parent.mkdir(exist_ok=True)
    fresh = not HISTORY.exists() or HISTORY.stat().st_size == 0
    wrote = False
    with HISTORY.open("a", newline="") as f:
        w = csv.writer(f)
        if fresh:
            w.writerow(HEADER)
        for r in rows:
            gap = str(r["status"]).startswith("GAP")
            obs = "" if gap else r["date"]
            if not gap and (r["id"], obs) in seen:
                continue
            w.writerow([run, obs, r["id"], "" if gap else r["latest"],
                        "GAP" if gap else r["status"]])
            wrote = True
    return wrote


def coverage() -> str:
    if not HISTORY.exists() or HISTORY.stat().st_size == 0:
        return ""
    runs = sorted({ln.split(",", 1)[0] for ln in HISTORY.read_text().splitlines()[1:] if ln})
    return f"Monitoring since {runs[0]} — {len(runs)} daily checks on record." if runs else ""


def main() -> None:
    lines = [f"# Tripwire check — {date.today().isoformat()}", ""]
    alert_class = None  # "TRIPWIRE" | "MONITOR-BROKEN"

    if not FRED_KEY:
        if IN_CI:
            alert_class = "MONITOR-BROKEN"
            lines.append("## MONITOR BROKEN")
            lines.append("Running in CI but `FRED_API_KEY` secret is missing — "
                         "the credit dials cannot update. Fix: repo Settings -> "
                         "Secrets and variables -> Actions.")
        else:
            lines.append("Market checks skipped locally: FRED_API_KEY not set "
                         "(free key: fred.stlouisfed.org).")
    else:
        rows, alerts = run_credit_checks()
        gaps = [r for r in rows if str(r["status"]).startswith("GAP")]

        lines.append("| Tripwire | Latest | Obs date | Status |")
        lines.append("|---|---|---|---|")
        for r in rows:
            if str(r["status"]).startswith("GAP"):
                lines.append(f"| {r['name']} | — | — | {r['status']} |")
            else:
                sess = f" ({r['sessions']}s)" if r.get("sessions", 1) > 1 else ""
                lines.append(f"| {r['name']}{sess} | {r['latest']} | {r['date']} | {r['status']} |")
        lines.append("")

        if gaps and len(gaps) == len(rows):
            alert_class = "MONITOR-BROKEN"
            lines.append("## MONITOR BROKEN")
            lines.append("Every fetch failed — likely an API change or network issue, "
                         "not a market event. The dials are blind until fixed.")
            lines.append("")
        elif gaps:
            lines.append(f"Note: {len(gaps)} dial(s) dark — investigate if it persists; "
                         "GAP rows are being recorded in history.csv.")
            lines.append("")

        if alerts:
            alert_class = alert_class or "TRIPWIRE"
            lines.append("## TRIPWIRE ALERTS")
            lines.extend(f"- {a}" for a in alerts)
            lines.append("")
            lines.append("Rule 10.7: read the refutation column first. If a refuting "
                         "condition fired and you're reaching for a reason it doesn't "
                         "count, the thesis has become a belief.")
        elif not gaps:
            lines.append("All quiet.")

        try:
            a = assess_stage(rows)
            if a["terminal"]:
                lines.append(f"**{a['name']}**")
            else:
                lines.append(f"**Stage {a['stage']} — {a['name']}** "
                             f"(computed {a['computed']}, floor {a['floor']}"
                             + (f"; {a['evidence_note']}" if a["evidence_note"] else "") + ")")
                if a["refute_overlay"]:
                    lines.append(f"- {a['refute_overlay']}")
                if a["baseline_expired"]:
                    lines.append("- Baseline prior expired unrenewed — floor dropped to 0.")
            lines.append("")
        except Exception as exc:  # logged, never swallowed (F23)
            lines.append(f"_Stage assessment unavailable: {exc}_")
            lines.append("")

        if append_history(rows):
            lines.append(f"_History snapshot written. {coverage()}_")

    Path("report.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if alert_class:
        Path("ALERT").write_text(alert_class + "\n")


if __name__ == "__main__":
    main()
