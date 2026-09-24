#!/usr/bin/env python3
"""Parse all jobs.json for entries whose last_error contains an error, mirroring
the watchdog's named-failure list. Fast, no slow `hermes cron list`."""
import glob, json, re

files = (glob.glob("~/.hermes/cron/jobs.json")
         + glob.glob("~/.hermes/profiles/*/cron/jobs.json"))

probs = []
drift = []
for f in files:
    try:
        data = json.load(open(f))
    except Exception:
        continue
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    home = f.split("/profiles/")[-1].split("/cron")[0] if "/profiles/" in f else "default"
    for j in jobs:
        le = str(j.get("last_error") or "")
        if "error" not in le.lower():
            continue
        # mirror watchdog: only report "error:" style reasons
        name = j.get("name") or j.get("id") or ""
        prov = j.get("provider")
        is_drift = "drift" in le.lower()
        probs.append((home, name, le.strip()[:160], prov, is_drift, j.get("id") or ""))

print("TOTAL error-last_error entries:", len(probs))
# categorize drift_skip vs others
drift_entries = [p for p in probs if p[4]]
non_drift = [p for p in probs if not p[4]]
print("drift_skip entries (should all be pinned now):", len(drift_entries))
for h, n, le, prov, d, jid in drift_entries:
    print(f"  [{h}] {n} prov={prov} id={jid[:12]} :: {le[:80]}")
print("non-drift entries:", len(non_drift))
for h, n, le, prov, d, jid in non_drift:
    print(f"  [{h}] {n} :: {le[:110]}")
print("TOTAL probs:", len(probs))