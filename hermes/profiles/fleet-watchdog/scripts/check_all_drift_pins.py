#!/usr/bin/env python3
"""Scan ALL jobs.json for drift_skip-styled jobs (provider null OR drift_alerted)
and report their provider/model to verify pin status."""
import glob, json

files = (glob.glob("~/.hermes/cron/jobs.json")
         + glob.glob("~/.hermes/profiles/*/cron/jobs.json"))

drift = []          # jobs flagged drift_alerted or last_error contains drift_skip
unpinned = []       # provider is null / missing  (candidates for future drift)
total = 0
for f in files:
    try:
        data = json.load(open(f))
    except Exception as e:
        print("ERR", f, e); continue
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    home = f.split("/profiles/")[-1].split("/cron")[0] if "/profiles/" in f else "default"
    for j in jobs:
        total += 1
        name = j.get("name") or j.get("id") or ""
        jid = j.get("id") or j.get("job_id") or ""
        prov = j.get("provider"); model = j.get("model")
        le = str(j.get("last_error") or "")
        da = j.get("drift_alerted")
        if "drift" in le.lower() or da:
            drift.append((home, jid, name, prov, model))
        if not prov:
            unpinned.append((home, jid, name))

print("TOTAL jobs:", total)
print("== drift-related jobs (le contains drift OR drift_alerted) ==")
for h, jid, name, prov, model in drift:
    print(f"  [{h}] {jid[:12]} {name}: prov={prov} model={model}")
print("== jobs with provider=null (future drift candidates) ==")
for h, jid, name in unpinned:
    print(f"  [{h}] {jid[:12]} {name}")
print("UNPINNED count:", len(unpinned))