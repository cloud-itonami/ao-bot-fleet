import glob, json, os, re
HOME="~/.hermes/profiles/fleet-watchdog"
import sys
sys.path.insert(0, os.path.join(HOME,"scripts"))
try:
    import fleet_cron_watchdog as w
    def_=os.path.expanduser("~/.hermes/.env")
    key=None
    if os.path.exists(def_):
        for line in open(def_):
            m=re.match(r'^OPENROUTER_API_KEY=..*(\S)',line)
            if m and not line.strip().startswith('#'): key=line.strip().split('=',1)[1]
    print("default .env exists:", os.path.exists(def_), "key:", bool(key))
    missing=[]
    for envf in glob.glob(os.path.expanduser("~/.hermes/profiles/*/.env")):
        prof=envf.split("/profiles/")[1].split("/.env")[0]
        has=False
        if os.path.exists(envf):
            for line in open(envf):
                if line.startswith("OPENROUTER_API_KEY=") and len(line.strip().split("=",1)[-1])>5: has=True
        if not has and not key: missing.append(prof)
    print("PROVIDER-MISSING-KEY(after fallback):", len(missing), missing[:10])
except Exception as e:
    print("ERR", e)

# drift pins: jobs the watchdog names as drift_skip this run
drift_jobs = {
 "design-audit-weekly":None,"coverage-gap-scout":None,"jv-migration-weekly":None,
 "model-scout-taxonomy-weekly":None,"seiri-cleanup-retirement-weekly":None,"wiki-kaonavi-crawl-scout":None}
homes=[os.path.expanduser("~/.hermes")]+glob.glob(os.path.expanduser("~/.hermes/profiles/*"))
unpinned=[]
for jf in [os.path.join(h,"cron","jobs.json") for h in homes]:
    if not os.path.exists(jf): continue
    try: data=json.load(open(jf))
    except Exception: continue
    jobs=data.get("jobs",data) if isinstance(data,dict) else data
    for j in jobs if isinstance(jobs,list) else []:
        if not isinstance(j,dict): continue
        if j.get("name") in drift_jobs:
            print("DRIFT:", j.get("name"), j.get("id"), "prov=",j.get("provider"), "model=",j.get("model"))
            if not j.get("provider"): unpinned.append((jf,j.get("name"),j.get("id")))
print("UNPINNED drift:",unpinned)
