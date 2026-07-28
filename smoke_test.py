"""smoke_test.py — first-contact test against the REAL FRED and SEC APIs (F18).
The build sandbox could never reach them; this settles response shapes and
measures the FRED observation lag the workflow comment guesses at.
Runs as an early CI step; degrades to a loud skip locally without keys."""
import sys
from datetime import date

import server

failures = 0

# ---- FRED ----
if not server.FRED_KEY:
    print("SKIP  FRED: FRED_API_KEY not set (in CI this is caught by check.py as MONITOR-BROKEN)")
else:
    try:
        obs = server.fred_latest("BAMLH0A0HYM2", 12)
        assert obs and isinstance(obs[0][1], float), f"unexpected shape: {obs[:2]}"
        lag = (date.today() - date.fromisoformat(obs[0][0])).days
        print(f"PASS  FRED fred_latest: {len(obs)} obs, latest {obs[0][0]} = {obs[0][1]}")
        print(f"INFO  FRED observation lag vs today: {lag} day(s) — if consistently >=1 at the "
              f"21:30 UTC cron, the 'after FRED update' workflow comment is wrong; history.csv's "
              f"obs_date column records the truth either way.")
        w = server.fred_window("BAMLH0A0HYM2", 10)
        assert len(w) == 10
        print("PASS  FRED fred_window: exactly 10 valid sessions")
        sp = server.spread_window("BAMLH0A3HYC", "BAMLH0A0HYM2", 15)
        assert sp, "empty CCC-HY spread window"
        print(f"PASS  FRED spread_window: {len(sp)} common dates, latest spread {sp[0][1]}")
    except Exception as e:
        failures += 1
        print(f"FAIL  FRED path: {type(e).__name__}: {e}")

# ---- EDGAR ----
try:
    server._require_ua()
    ua_ok = True
except RuntimeError as e:
    ua_ok = False
    print(f"SKIP  EDGAR: {e}")
if ua_ok:
    try:
        filings = server.edgar_recent("nvidia", "10-Q", 2)
        assert filings and filings[0]["url"].startswith("https://www.sec.gov/")
        print(f"PASS  EDGAR submissions: latest NVDA 10-Q filed {filings[0]['filed']}")
        res = server.edgar_fulltext('"equity cure"', company="coreweave")
        total = res.get("hits", {}).get("total", {}).get("value")
        assert isinstance(total, int), f"unexpected efts shape: {list(res)[:5]}"
        print(f"PASS  EDGAR full-text: {total} hits for \"equity cure\" @ CoreWeave")
    except Exception as e:
        failures += 1
        print(f"FAIL  EDGAR path: {type(e).__name__}: {e}")

if failures:
    print(f"\n{failures} live-shape failure(s) — the monitor's fetchers do not match the real "
          f"APIs. Treat as MONITOR-BROKEN.")
    sys.exit(2)
print("\nSMOKE TEST COMPLETE")
