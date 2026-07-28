# bubble-monitor

A monitoring system for the thesis in *The Useful Life of a Bubble* (July 2026),
built on its Section 10 tripwires and calendar. One codebase, two entry points:

- **`server.py`** — an MCP server, so Claude (Desktop or Code) can fetch spreads,
  search EDGAR, list tripwires, and keep your prediction journal *while you talk to it*.
- **`check.py`** — a cron entry point. GitHub Actions runs it every weekday after
  the US close and opens an issue in this repo when a threshold crosses.

The division of labor is deliberate: **the machine fetches and checks; you read
the filings and score the calls.** Every number is fetched, never recalled; a
failed fetch reports as a GAP, never a guess (the report's [V]/[G] discipline).

## Setup (any ordinary folder — ~20 minutes)

```bash
mkdir bubble-monitor && cd bubble-monitor      # drop these files in
git init
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export FRED_API_KEY="..."       # free: fred.stlouisfed.org -> My Account -> API Keys
export EDGAR_UA="bubble-monitor your-email@university.edu"   # SEC asks clients to identify themselves

python selftest.py              # offline regression suite (the red-team fixture tests)
python smoke_test.py            # first LIVE contact with FRED + SEC — also measures
                                # the FRED observation lag (see its INFO line)
python check.py                 # first live pull — should print the credit table
```

## Connect the MCP server to Claude

Add an entry to your Claude Desktop MCP configuration pointing at this server —
current instructions and the config file location for your OS are at
https://docs.claude.com (search "MCP"). The entry has this shape:

```json
{
  "mcpServers": {
    "bubble-monitor": {
      "command": "/absolute/path/to/bubble-monitor/venv/bin/python",
      "args": ["/absolute/path/to/bubble-monitor/server.py"],
      "env": { "FRED_API_KEY": "...", "EDGAR_UA": "bubble-monitor your-email" }
    }
  }
}
```

Restart Claude Desktop and try: *"check my credit tripwires"* or *"any new
CoreWeave 8-Ks?"*. Claude Code can attach the same server for use while you
iterate on the code itself.

## Automate it (Level 2)

1. Push this folder to a **public** GitHub repo (public = your timestamped track record).
2. Repo Settings -> Secrets and variables -> Actions: add `FRED_API_KEY` and `EDGAR_UA`.
3. Done. `.github/workflows/daily_check.yml` runs weekdays at 21:30 UTC and opens
   an issue titled "Tripwire alert" the day anything crosses. Use the
   *workflow_dispatch* button in the Actions tab to test it immediately.

## The event-day workflow (the part that builds the skill)

For each date in `calendar.json` (ask Claude: *"what's coming up?"*):

1. **Before** — `log_prediction`: what you expect the print to show, and why.
2. **Event** — pull the filing (`latest_filings('meta','10-Q')`), and **read the
   relevant passage yourself**. Use Claude for triage ("diff the useful-life
   language vs last quarter"), not for replacement reading.
3. **After** — `score_prediction`: what actually printed, right/wrong/mixed, lesson.
4. Commit. The journal + commit history *is* the public record.

## Rules (non-negotiable)

- **Refutation column first** (report Sec 10.7). The tripwires exist to prove
  the thesis wrong as much as right.
- **No number without a fetch.** If a tool errors, it's a gap, not an estimate.
- **Negative findings are fragile.** Zero EDGAR hits proves less than it seems —
  see the report's own Oracle miss (Sec 12.3.7) before trusting an absence.
- **No trading logic in this repo, ever.** Paper journal only. CDS levels are
  paywalled everywhere (the report tagged them [R] for the same reason); the
  free FRED spread series are the stress dials.

## From your phone

Three tiers, in order of effort:

**1. Push alerts (5 min).** Install the GitHub mobile app and watch your own
repo. The tripwire-alert issues the cron opens become push notifications. The
Actions tab's manual-run button also works from the app, so you can trigger a
check on demand from anywhere.

**2. The glance dashboard (one repo setting).** The workflow builds
`docs/index.html` — a mobile-first status page (filing-stamp status, spread
dials with confirm/refute rails, event countdowns, your journal) — and deploys
it to GitHub Pages on every run. Enable it once: repo **Settings -> Pages ->
Source: GitHub Actions**. Your URL becomes
`https://<username>.github.io/<repo>/`; open it on your phone and use
**Add to Home Screen** for the app-icon experience. It updates every weekday
close and on every commit.

**3. Conversational access (optional, later).** The MCP server currently runs
stdio (same-machine). The SDK also supports `mcp.run(transport="streamable-http")`,
so it can be deployed as a *remote* MCP server on a small host and added to
Claude as a custom connector, making the tools available in the Claude mobile
app ("check my tripwires" from the bus). Put authentication in front of it —
never expose an open tool server — and see https://docs.claude.com and
https://support.claude.com for current custom-connector setup and plan
availability.

Note the deliberate design: alerts push to you on exception; the dashboard is a
glance, not a feed. A monitoring system you check compulsively has become the
thing it was built to study.

## Keeping it alive for years

Multi-year systems die in a known order: scrapers, then schedulers, then APIs,
then data, then the maintainer. Defenses built in and defenses that are yours:

**Built in.** The daily run commits its own `data/history.csv` snapshot — that
commit is a heartbeat that stops GitHub from disabling the schedule on an
"inactive" repo (it does, after ~60 days without activity), and it accumulates
your own plain-text dataset of every dial, every day. A **monitor-broken**
alert (all fetches failing, or the FRED secret missing in CI) is distinct from
a **tripwire** alert, so the system cannot fail silently. Everything is plain
text in git: readable in 2035, no database, no server, no migration.

**Yours — three small rituals (rituals outlast scrapers):**
1. *Quarterly, ~20 min, after each earnings season:* replenish `calendar.json`
   (confirm [EST] dates, add next quarter's), update each manual tripwire's
   `current` + as-of after your event-day reads, renew `_meta.baseline_review_by`
   (or deliberately let the prior expire to 0), and confirm the Actions tab
   shows green runs — a platform-side disablement is the one failure no code
   here can catch.
2. *Commit tripwires.json immediately after `set_tripwire_state`* — the site
   renders committed state only; an uncommitted laptop state is invisible.
   And *never move a threshold without a commit message saying why.* Git history is
   your anti-goalpost-moving log — the report corrected its own premises in
   writing (Sec 12.3); so do you.
3. *Quarterly "state of the thesis" memo in the journal* — and define the
   endgame: the thesis is OPEN until you mark it CONFIRMED, REFUTED, or REVISED
   with evidence. A dashboard nobody can close becomes a zombie.

**Watch the meta-risk the report itself flags (Sec 10.6):** if SEC proposal
S7-2026-15 (optional semiannual reporting) is adopted and issuers elect it,
half the observation points here disappear. That belongs on your calendar the
day it gets an effective date.

## The site

`docs/` is a small standalone website served by GitHub Pages: **index.html**
(the live appendix), **thesis.html** (the report page — drop the PDF at
`docs/thesis.pdf`), and the **stage assessment** — a button that runs declared
rules over every tracked signal (auto dials + the manual states you record via
`set_tripwire_state`) and shows the stage with full evidence, the baseline
prior, and the refute path. The rules live in `server.py` (`assess_stage`) in
plain sight; changing them is allowed, hiding the change is not. Note: a public
repo means a public PDF — if you'd rather keep the report private, the GitHub
Student Developer Pack includes Pro, which allows Pages on private repos
(verify current terms on github.com/education — and note private repos meter
Actions minutes, which changes the free-tier calculus).

## Files

```
server.py                        MCP server (tools) + core fetch/check functions
check.py                         cron entry point -> report.md (+ classed ALERT file)
build_dashboard.py               renders docs/index.html for GitHub Pages
data/history.csv                 append-only readings, v2: run_date,obs_date,id,value,status
                                 (GAP rows included — outages are data, not holes)
selftest.py                      offline regression suite (runs first in CI)
smoke_test.py                    live API shape test (runs second in CI)
BACKLOG.md                       deferred items + the review findings register
docs/                            the website: index.html, thesis.html, thesis.pdf
tripwires.json                   Section 10.4, machine-readable (edit as facts update)
calendar.json                    Section 10.2-10.3 dated events
journal.jsonl                    created at first log_prediction — append-only
.github/workflows/daily_check.yml  weekday automation
```

*Research/education tooling only. Nothing here is investment advice.*
