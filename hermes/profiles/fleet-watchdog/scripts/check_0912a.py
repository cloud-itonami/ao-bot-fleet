import json, os, re, glob

homes = ["~/.hermes"] + glob.glob(os.path.expanduser("~/.hermes/profiles/*"))
# 1) default .env key
denv = os.path.expanduser("~/.hermes/.env")
def keyval(path):
    if not os.path.exists(path):
        return None
    for line in open(path):
        line = line.strip()
        if line.startswith("OPENROUTER_API_KEY=") and len(line.split("=",1)[1]) > 5:
            return line.split("=",1)[1][:8]
    return None
key = keyval(denv)
print("default .env exists:", os.path.exists(denv), "key:", bool(key))

# 2) provider-missing-key per profile (watchdog-like: fallback to default)
canon = os.path.expanduser("~/.hermes/profiles/hyakka-crawl/.env")
ckey = keyval(canon) or key
missing = []
for h in homes:
    name = "default" if h.endswith(".hermes") else os.path.basename(h)
    prov = None
    for p in [os.path.join(h, "config.yaml")]:
        if os.path.exists(p):
            m = re.search(r"^\s*provider:\s*([\w-]+)", open(p).read(), re.M)
            if m: prov = m.group(1)
    if prov and prov not in ("openrouter", "openrouter-free"):
        continue
    env = os.path.join(h, ".env")
    k = keyval(env)
    if k is None and key is None:
        missing.append(name)
print("PROVIDER-MISSING-KEY:", missing or "0")

# 3) drift pins: load all jobs.json, find drift_alerted jobs w/ prov=None
unpinned, drift_n = [], 0
for h in homes:
    jj = os.path.join(h, "cron", "jobs.json")
    if not os.path.exists(jj): continue
    try:
        data = json.load(open(jj))
    except Exception as e:
        print("ERR", jj, e); continue
    for j in data.get("jobs", []):
        if j.get("drift_alerted"):
            drift_n += 1
            if not j.get("provider"):
                unpinned.append((os.path.basename(h) or "default", j.get("id"), j.get("name") or j.get("prompt","")[:40]))
print("drift_alerted jobs:", drift_n, "unpinned:", unpinned or "0")

# 4) last_error census from jobs.json
from collections import Counter
cats = Counter()
for h in homes:
    jj = os.path.join(h, "cron", "jobs.json")
    if not os.path.exists(jj): continue
    try:
        data = json.load(open(jj))
    except Exception: continue
    for j in data.get("jobs", []):
        le = (j.get("last_error") or "")
        if not le: continue
        n = os.path.basename(h) or "default"
        if "402" in le: c="402 credits"
        elif "429" in le and "murakumo" in le: c="429 murakumo"
        elif "429" in le: c="429 other"
        elif "Broken pipe" in le: c="broken pipe"
        elif "Connection error" in le or "connection" in le.lower(): c="connection error"
        elif "Gateway shutdown" in le or "Interrupted" in le: c="gateway/interrupted stale"
        elif "exited with code" in le: c="script exit"
        elif "Context length" in le: c="context length"
        elif "drift_skip" in le: c="drift_skip"
        elif "401" in le or "403" in le: c="401/403"
        elif "would exceed your available credits" in le: c="402 in-flight credits"
        else: c="other"
        cats[c]+=1
print("last_error census:", dict(cats.most_common()))
