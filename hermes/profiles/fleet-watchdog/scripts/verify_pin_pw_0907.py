#!/usr/bin/env python3
"""Verify the 10 pinned drift jobs now have provider/model in jobs.json."""
import glob, json

targets = {
    "62204614f8fa": (["design-audit"], "design-audit-weekly"),
    "c0f24f402770": (["isekai-x402"], "x402-price-diff-daily"),
    "f288d9331267": (["oppai-gen"], "oppai-report"),
    "d08b199efa22": (["murakumo-tok"], "murakumo-tok-tick"),
    "c56107d6ad5f": (["oriru"], "oriru-application-pulse"),
    "076b0d288cbf": (["samu"], "samu-blueprint-registry-watch"),
    "312f602e1569": (["seiri"], "seiri-cleanup-retirement-weekly"),
    "29cfd33c0076": (["seiri"], "seiri-weekly-audit"),
    "17207ee36d78": (["tobari"], "tobari-weekly-standup"),
    "c9c30f472c4d": (["tsuushin"], "tsuushin-daily"),
}
want_prov = "openrouter-free"
want_model = "deepseek/deepseek-v4-flash-0731"

files = (glob.glob("~/.hermes/cron/jobs.json")
         + glob.glob("~/.hermes/profiles/*/cron/jobs.json"))
all_ok = True
for f in files:
    try:
        data = json.load(open(f))
    except Exception:
        continue
    jobs = data.get("jobs", []) if isinstance(data, dict) else data
    for j in jobs:
        jid = j.get("id") or j.get("job_id") or ""
        if jid in targets:
            prov, model = j.get("provider"), j.get("model")
            good = (prov == want_prov and model == want_model)
            all_ok &= good
            print(f"{jid[:12]} {j.get('name')}: prov={prov} model={model} -> {'PINNED-OK' if good else 'NOT-OK @ '+f}")
print("ALL_OK:", all_ok)