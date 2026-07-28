# BACKLOG — deferred by decision, not by accident

Findings register: the adversarial review of 2026-07-28 (F-numbers). Everything
P0/P1 and every S-effort P2/P3 was fixed the same day; what remains here was
deferred deliberately, each with its trigger. Reviewer calibration: all ten
disclosed soft spots were caught, plus nine confirmed-by-execution bugs.

## Deferred items

1. **F17 — directional threshold schema.** Replace `confirm_gt/refute_lt` with
   `confirm:{op,value,sessions}` / `refute:{op,value,sessions}` so inverted
   dials (GE Vernova `<120 GW`, DLR spreads) can ever be automated safely.
   The seam exists: only `server.evaluate()` touches thresholds now.
   *Trigger: the first time any inverted manual tripwire is automated.*

2. **F23 — unresolved-rituals strip.** Dashboard section listing predictions
   without scores and manual tripwires whose `when` has passed with no
   `state_as_of` — so "quiet market" and "absent maintainer" stop looking
   identical. *Trigger: first quarterly review (2026-10-31).*

3. **States as events.** Replace in-place mutation of tripwires.json with an
   append-only `states.jsonl` (current state = fold of events), eliminating the
   laptop/site split-brain and making every judgment timestamped and reasoned
   by construction. *Trigger: alongside item 2.*

4. **Measure → Record → Render.** The reviewer's architecture: one fetch per
   run appends to history.csv as the system of record; evaluate() reads windows
   from the CSV; sparklines come from the archive (which also makes the
   licensed-series risk self-hedging — a withdrawn ICE BofA series freezes over
   its own history with a `series_withdrawn` badge instead of amnesia; the one
   free labeled degraded-mode substitute worth considering is STLFSI4, never a
   silent replacement). *Trigger: ~90 days of history.csv accumulated.*

5. **SHA-pin the four actions (F20, one-time setup task).** From an
   authenticated machine:
   `gh api repos/actions/checkout/commits/v4 -q .sha` (repeat for
   setup-python@v5, upload-pages-artifact@v3, deploy-pages@v4), paste into the
   workflow. Tag pins ship until then — inventing SHAs would be an F9-class sin.

6. **Self-host the two fonts** (F21 privacy nicety) into docs/ if the Google
   Fonts dependency ever bothers you; system fallbacks already degrade cleanly.

7. **Merge the reviewer's `redteam_tests.py`.** It exists in the review
   sandbox, not here — ask that conversation to print the file, then fold any
   cases selftest.py lacks.

## Removed per review

- **F4:** `bet_sizing_sim.py` removed from the repo (public credibility record
  is the wrong home for bet-sizing code; the no-trading-logic boundary reads
  strictly in public). The standalone educational copy delivered earlier in the
  build conversation remains the owner's — this was a placement fix, not a
  disavowal.
