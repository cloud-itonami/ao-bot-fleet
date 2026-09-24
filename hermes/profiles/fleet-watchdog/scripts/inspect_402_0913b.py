import json, os, glob
homes = ["~/.hermes"] + glob.glob(os.path.expanduser("~/.hermes/profiles/*"))
provs = {}
for h in homes:
    jj = os.path.join(h, "cron", "jobs.json")
    if not os.path.exists(jj): continue
    try:
        data = json.load(open(jj))
    except Exception: continue
    for j in data.get("jobs", []):
        le = (j.get("last_error") or "")
        if "402" in le:
            k = (j.get("provider"), j.get("model"))
            provs.setdefault(k, []).append((os.path.basename(h) or "default", j.get("id")))
for k, v in sorted(provs.items(), key=lambda x: -len(x[1])):
    print(k, len(v), [x[0] for x in v[:5]])
