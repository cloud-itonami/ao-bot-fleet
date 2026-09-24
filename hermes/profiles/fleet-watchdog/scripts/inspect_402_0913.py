import json, os, glob, datetime

homes = ["~/.hermes"] + glob.glob(os.path.expanduser("~/.hermes/profiles/*"))
rows = []
for h in homes:
    jj = os.path.join(h, "cron", "jobs.json")
    if not os.path.exists(jj):
        continue
    try:
        data = json.load(open(jj))
    except Exception:
        continue
    prof = os.path.basename(h) or "default"
    for j in data.get("jobs", []):
        le = (j.get("last_error") or "")
        if "402" in le or "credits" in le:
            rows.append({
                "profile": prof,
                "id": j.get("id"),
                "name": (j.get("name") or "")[:60],
                "provider": j.get("provider"),
                "model": j.get("model"),
                "drift_alerted": j.get("drift_alerted"),
                "last_run": j.get("last_run"),
                "err": le[:180],
            })

print("402/credits jobs:", len(rows))
for r in sorted(rows, key=lambda x: str(x.get("last_run") or ""), reverse=True)[:45]:
    print(json.dumps(r, ensure_ascii=False))

# also: model distribution across ALL fleet jobs (to see what pin targets are common)
from collections import Counter
md = Counter()
for h in homes:
    jj = os.path.join(h, "cron", "jobs.json")
    if not os.path.exists(jj):
        continue
    try:
        data = json.load(open(jj))
    except Exception:
        continue
    for j in data.get("jobs", []):
        md[(j.get("provider"), j.get("model"))] += 1
print("\nALL-JOB (provider, model) distribution:")
for k, v in md.most_common(20):
    print(v, k)
