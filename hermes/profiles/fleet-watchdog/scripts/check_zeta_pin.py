#!/usr/bin/env python3
"""Find drift_skip / unpinned jobs: scan all jobs.json for jobs that are
drift-alerted or unpinned (provider null) and report pin status."""
import glob, json

paths = glob.glob("~/.hermes/profiles/*/cron/jobs.json") + ["~/.hermes/cron/jobs.json"]
targets = ["zeta", "adnetwork-scout", "legal-disclosure-crawl-scout",
           "server-operator-crawl-scout", "whois-org-crawl-scout",
           "wiki-govstats-crawl-scout", "wiki-patent-crawl-scout"]
all_jobs = []
for p in paths:
    try:
        data = json.load(open(p))
    except Exception:
        continue
    for jb in data.get("jobs", []):
        parts = p.split("/profiles/")
        home = parts[1].split("/cron")[0] if len(parts) > 1 else "default-home"
        all_jobs.append((home, jb))

for home, jb in all_jobs:
    name = str(jb.get("name", ""))
    prov = jb.get("provider")
    model = jb.get("model")
    drift_alerted = jb.get("drift_alerted")
    if any(t in name for t in targets):
        status = "PINNED" if prov and model else "UNPINNED"
        print(f"[{home}] id={jb.get('id')} name={name!r} prov={prov} model={model} -> {status} drift_alerted={drift_alerted}")

print("---- UNPINNED jobs (provider null) with drift_alerted True across fleet ----")
for home, jb in all_jobs:
    prov = jb.get("provider")
    if not prov and jb.get("drift_alerted"):
        print(f"[{home}] id={jb.get('id')} name={str(jb.get('name'))!r} drift_alerted={jb.get('drift_alerted')} last_run={jb.get('last_run','')}")