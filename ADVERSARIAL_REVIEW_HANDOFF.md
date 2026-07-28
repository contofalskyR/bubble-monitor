# ADVERSARIAL REVIEW HANDOFF — "bubble-monitor"

## Your role

You are the red team. Another Claude agent built this system with me over one long
session; assume the builder was competent but motivated — it wanted the system to
work and to look good, which is exactly the bias that hides flaws. Your job is to
find where this system **breaks, rots, silently lies, or flatters its owner**, and
to strengthen it with concrete fixes. Do not soften findings. Do not praise-sandwich.
If something is good, one line is enough; spend your tokens on what's wrong.

If you need an artifact you weren't given (a runtime log, a rendered screenshot, a
file mentioned but not attached), **ask for it — never guess its contents.**

## Who this is for, and the constraints that set severity

- Owner: a PhD student on a ~$40k stipend. Paper-tracking only. **No trading logic,
  ever** — that is a hard product boundary, not a gap.
- Horizon: this must run and stay trustworthy through at least mid-2028 with months-long
  maintainer absences. Longevity failures are severe; missing features are not.
- Infra budget: $0. Free GitHub Actions + Pages, free FRED API key, public SEC APIs.
  Any fix requiring paid infra is out of bounds.
- Primary goal: the owner is *learning* credit analysis by running this. The system's
  epistemics (never overstating what it knows) outrank its polish.

## What the system is

It monitors the thesis of an attached forensic research report, *The Useful Life of a
Bubble* (25 Jul 2026): the AI infrastructure buildout is two trades priced as one —
cash-rich hyperscalers (defensible) vs. a levered periphery (Oracle, CoreWeave, SPVs,
private credit) financing decade assets with four-year money. The report's Section 10
defines dated calendar events and ~27 "tripwires," each with an explicit CONFIRM
threshold *and* an equal-weight REFUTE threshold (its Rule 10.7: read the refutation
column first).

Components (all attached):

1. **tripwires.json** — Section 10.4 transcribed to machine-readable form. 6 dials
   auto-checkable via FRED; 23 manual (filing reads). `_meta` declares a
   `baseline_stage: 1` prior with rationale. Manual entries may carry
   `state / state_as_of / state_note` set by the owner on event days.
2. **calendar.json** — Section 10.2/10.3 dated events, [V]/[EST] tagged, four flagged
   `load_bearing`.
3. **server.py** — MCP server (SDK 2.x with 1.x fallback shim) exposing 11 tools:
   `check_credit_tripwires`, `fred_series`, `edgar_search` (efts.sec.gov full-text),
   `latest_filings` (data.sec.gov submissions), `list_tripwires`, `upcoming_events`,
   `log_prediction`, `score_prediction`, `journal_review`, `set_tripwire_state`,
   `assess_thesis_stage`. Core plain functions are importable by the cron path.
   Contains `assess_stage()`: ten declared rules mapped to stages 0–4, stage =
   max(computed, baseline prior), plus a refute-overlay that fires when refutations
   dominate.
4. **check.py** — cron entry point. Runs the FRED checks, writes report.md, touches
   `ALERT` on threshold crossings, appends `data/history.csv` (long format
   date,id,value,status; dedupes by run date), and has a dead-man's switch:
   monitor-broken alert when *all* fetches fail or the FRED secret is missing in CI.
5. **daily_check.yml** — GitHub Actions: cron 21:30 UTC weekdays + push-to-main +
   manual dispatch. Commits the history snapshot back with `[skip ci]` (deliberately:
   the commit is a heartbeat defeating GitHub's ~60-day inactive-schedule disablement),
   deploys `docs/` to Pages, opens an issue when `ALERT` exists.
6. **build_dashboard.py** — renders a two-page static site: `index.html` (status
   stamp, pulse strip, six dial cards with sparklines, 30-day deltas, dual-threshold
   gauges, proximity "warming" at ≥70%, timeline calendar, manual tripwires with
   state badges, journal tail, footer coverage line) and `thesis.html` (report §1.1 +
   link to `thesis.pdf`), plus a **stage assessment button** that reveals the ten
   rule evaluations and the stage stamp, computed at build time. `--sample` mode
   renders a labeled UI preview from the report's 25 Jul values.

## The principles the system CLAIMS to embody — test the code against each

For each principle, find at least one place the implementation betrays it:

1. **Fetch, never recall** — no number reaches the owner that wasn't fetched; failures
   surface as [G] gaps, never estimates.
2. **Refute-first symmetry** — refutation conditions get equal prominence everywhere.
3. **Automate plumbing, human does judgment** — filings are read by the owner; the
   machine only retrieves, checks, journals.
4. **Rituals over scrapers** — quarterly-frequency data is maintained by documented
   human ritual, not fragile scraping.
5. **Self-sustaining** — heartbeat commits; a dead-man's switch; cannot die silently.
6. **Plain text + git durability** — readable in 2035; threshold changes must be
   visible in git history ("changing rules is allowed, hiding the change is not").
7. **Anti-engagement design** — quiet looks quiet; alerts push on exception; nothing
   rewards compulsive checking.
8. **No trading logic, no auto-anything touching markets.**

## Soft spots I'm handing you — confirm, extend, and fix

The builder is aware of these; verify severity and propose patches:

- **history.csv date semantics**: rows are stamped with the *run* date, but FRED
  observations may be from the prior day (21:30 UTC run vs. series update lag). The
  dataset conflates run-date and observation-date. What's the right schema fix?
- **Directional schema assumption**: proximity, gauges, and the stage engine all
  assume `confirm_gt > refute_lt` (stress = up). Several *manual* tripwires invert
  (e.g., GE Vernova: CONFIRM is `<120 GW`). If any inverted dial is ever automated,
  prox/gauge/engine silently mislead. Design the schema for direction.
- **The baseline prior floors the stage**: `stage = max(computed, baseline)` means a
  thesis drowning in refutes still displays "Stage 1." The refute overlay exists, but
  should accumulating refutes decay or suspend the prior? Argue it both ways, then
  pick.
- **Threshold boundary semantics**: code uses strict `>` / `<`; the report writes
  ">4.50% for 10 sessions" and "<2.50% sustained." The 10-session window is applied
  to HY confirm *and* refute; every other dial is judged on a single print. Check
  each against §10.4.1's exact wording.
- **Alert-issue spam**: a persistently broken monitor (or persistent crossing) opens
  a same-titled issue every day; multiple same-day dispatch runs may duplicate.
  Propose dedupe (search open issues? update-in-place?).
- **Reduced-motion is incomplete**: bubbles are disabled under
  `prefers-reduced-motion`, but the stage-panel `.crit` stagger still animates.
- **Default `EDGAR_UA` has no contact info** — SEC fair-access guidance expects an
  identifying User-Agent with contact; the fallback string doesn't comply.
- **Never rendered in a real browser**: all HTML was verified by string probes in a
  sandbox; no screenshot, no mobile test. Google Fonts is an external runtime
  dependency (availability + privacy).
- **Licensed FRED series risk**: the ICE BofA OAS series are third-party-licensed
  data on FRED; licensed series have historically been restricted or withdrawn.
  There is no fallback source. Design one (or a graceful degradation).
- **Live network paths are untested**: the build sandbox could not reach FRED or
  SEC endpoints, so `fred_latest`, `edgar_fulltext`, `edgar_recent` have never
  executed against real APIs. Param names were verified against documentation only.
  Treat all network code as unproven.

## Attack checklist — do all eight

1. **Transcription fidelity (highest value).** Diff `tripwires.json` and
   `calendar.json` line-by-line against the attached report's §10.2–10.4. Any
   threshold, date, current value, or condition that drifted from the source is a
   P0/P1 — this system's entire authority is fidelity to that document. Also audit
   the thesis paragraph on `thesis.html` against §1.1.
2. **Code correctness.** Trace `run_credit_checks` per check type; boundary values
   (exactly at threshold); empty/short FRED responses; the fred_spread date-alignment
   logic; `date.today()` timezone behavior on a UTC runner; the MCP 1.x/2.x shim; the
   sample-mode generator (could its fake wiggle ever cross a threshold and render a
   fake alert?).
3. **Failure injection.** Enumerate every way this dies *silently despite* the
   dead-man's switch: Pages deploy job fails while check job succeeds; artifact
   upload fails; `git push` rejected on races; GitHub policy changes; secret
   rotation/expiry; Actions minute exhaustion; `[skip ci]` behavior changes. For
   each: detection + mitigation on free tier.
4. **Stage-engine epistemics.** Attack each of the ten rules' thresholds; propose the
   strongest alternative ruleset; stress the prior; construct a scenario where the
   engine says something a careful human reader of the same data would call wrong.
   Verify the engine is *capable* of declaring the thesis dead.
5. **Security.** MCP tool inputs (`set_tripwire_state`, journal writes) →
   file-write surface; every user-originated string that reaches HTML (journal
   entries, state notes, tripwire text) → escaping audit; workflow permission
   minimality; fork-PR secret exposure; supply chain (actions pinned by tag, not
   SHA; pip unpinned upper bounds).
6. **Longevity audit.** Table every external dependency (GitHub features, FRED, SEC
   endpoints, MCP SDK, Google Fonts, action versions, Python version) with a rot
   forecast and mitigation.
7. **Human factors.** Will the quarterly rituals actually happen? Propose friction
   reducers (issue templates? scheduled reminder issues?). Read every sentence of UI
   copy under Rule 10.7: does anything nudge toward confirmation bias? Does the
   stage button's theater risk overtrust in a hand-rolled classifier?
8. **The 2028 postmortem.** Write it as if it is mid-2028 and the system either died
   or — worse — kept running while quietly misleading its owner. Rank the most
   probable causes. This is the single most valuable section; be imaginative and
   specific.

## Deliverable format (strict)

1. **Findings table**: ID · Severity · Component · Finding · Evidence/repro ·
   Proposed fix · Effort (S/M/L).
   Severity calibration: **P0** = a number displayed as verified can be wrong or
   stale with no indication; **P1** = the pipeline can die or mislead silently;
   **P2** = epistemic/design weakness or fidelity drift; **P3** = polish.
2. **Top-5 patches**, with concrete code diffs or precise pseudocode.
3. **One page: "what I'd rebuild differently"** — architecture-level, respecting the
   constraints.
4. Rules: cite file + function/anchor for every finding; mark anything you couldn't
   reproduce as *speculative*; keep three categories separate — code bug, design
   disagreement, epistemic risk.

## Out of scope — do not propose

Trading or brokerage integration of any kind; paid infrastructure; scraping
earnings-calendar or price websites; turning this into a multi-user product; anything
that increases engagement pressure on the owner. The anti-engagement stance and the
paper-only boundary are features. Strengthen the instrument; don't change what it is.
