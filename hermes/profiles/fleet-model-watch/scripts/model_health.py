#!/usr/bin/env python3
"""Fleet model-assignment health monitor — decision-free measurement.

Reads every profile's cron/jobs.json + scheduler agent.log, computes per-model
ok-rates since the last ledger entry, appends one JSONL line to the ledger.
Exit codes: 0 measured and appended / 2 REFUSED (could not measure).
This is a --no-agent script job: no model tokens are spent by this job itself.
"""
import json, os, re, subprocess, sys, time, collections, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PROFILES = os.path.expanduser("~/.hermes/profiles")
LEDGER = os.path.join(HERE, "model-health-ledger.jsonl")
MANIFEST = os.path.join(os.path.dirname(HERE), "model-assignment-proposal.json")

def refuse(why):
    print("REFUSED — ledger not appended.")
    print(why)
    sys.exit(2)

def main():
    if not os.path.exists(MANIFEST):
        refuse(f"no manifest at {MANIFEST}")
    manifest = json.load(open(MANIFEST))
    job_model = {(j["profile"], j["job_name"][:60]): j["proposed_model"] for j in manifest}

    # last ledger timestamp = measurement window start
    since = 0
    if os.path.exists(LEDGER):
        lines = open(LEDGER).read().strip().splitlines()
        if lines:
            since = json.loads(lines[-1]).get("ts", 0)
    now = time.time()
    window_h = (now - since) / 3600 if since else None

    # scheduler-log outcomes per job since window start
    outcomes = collections.defaultdict(lambda: {"ok": 0, "fail": 0})
    per_model = collections.defaultdict(lambda: {"ok": 0, "fail": 0, "in_tok": 0, "out_tok": 0})
    # per-model latency distribution: cold-scale-model calls (qwen3.8 cyber,
    # glm cyber) routinely pay 150-190 s restores and post-deploy ~1600 s
    # snapshot rebuilds; a bare ok/fail rate reads those as instability.
    # Counting latency lets the ledger separate a slow-but-200 cold call from
    # a real failure (the watch must not answer what it cannot distinguish).
    lat_by_model = collections.defaultdict(list)
    COLD_SUSPECT_S = 120  # gateway restore for these origins is 87-190 s measured
    fault_sigs = collections.Counter()
    FAULTS = ["provider resolve failed", "drift_skip", "requires more credits",
              "127.0.0.1:9180", "at capacity", "Unknown provider"]

    for prof in os.listdir(PROFILES):
        log = os.path.join(PROFILES, prof, "logs", "agent.log")
        if not os.path.exists(log):
            continue
        try:
            res = subprocess.run(
                ["bash", "-c", f"grep -E \"Job '.*' (completed successfully|failed)|API call #|{'|'.join(FAULTS)}\" {log} | tail -400"],
                capture_output=True, text=True)
        except Exception as exc:
            refuse(f"cannot read {log}: {exc}")
        for line in res.stdout.splitlines():
            m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", line)
            if not m:
                continue
            try:
                ts = time.mktime(time.strptime(m.group(1), "%Y-%m-%d %H:%M"))
            except Exception:
                continue
            if ts <= since:
                continue
            for f in FAULTS:
                if f in line:
                    fault_sigs[f] += 1
            jm = re.search(r"Job '([^']+)'", line)
            if jm and ("completed successfully" in line or " failed" in line):
                st = "ok" if "completed successfully" in line else "fail"
                model = job_model.get((prof, jm.group(1)[:60]))
                if model:
                    outcomes[(prof, jm.group(1)[:60])][st] += 1
                    per_model[model][st] += 1
            mc = re.search(r"model=([\w/.:-]+) .*?in=(\d+) out=(\d+)", line)
            if mc and "API call #" in line:
                model = mc.group(1)
                d = per_model.setdefault(model, {"ok":0,"fail":0,"in_tok":0,"out_tok":0})
                d["in_tok"] += int(mc.group(2)); d["out_tok"] += int(mc.group(3))
                lm = re.search(r"latency=([\d.]+)s", line)
                if lm:
                    lat_by_model[model].append(float(lm.group(1)))

    # job-level status from jobs.json (drift_skip detection: status stuck non-ok while log says ok)
    drift = 0
    for (prof, name) in job_model:
        cj = os.path.join(PROFILES, prof, "cron", "jobs.json")
        try:
            data = json.load(open(cj)); js = data.get("jobs", data)
        except Exception:
            continue
        for x in js:
            if (x.get("name") or "")[:60] == name and x.get("last_status") == "error":
                drift += 1
                break

    # usagi (ling-3.0-tiny) window drift check — ADR-2609131642 policy 5.
    # The window's SOURCE is the node unit --ctx-size; ②gateway worker.cljk
    # (/v1/models context_window) ③model_token_limits.js (admission 400 body)
    # ④KV descriptor (catalog context) are mirrors. A mirror lagging the node
    # kills callers in one of three measured ways (Hermes 64K init gate,
    # auxiliary gate, gateway 400) while everything still answers on the node.
    # This check only ANNOUNCES divergence; it never edits anything.
    window_check = {}
    try:
        unit = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=10", "-i",
             os.path.expanduser("~/.ssh/murakumo"), "root@100.66.205.17",
             "grep -o 'ctx-size [0-9]*' /etc/systemd/system/murakumo-edge-usagi-llama.service | grep -o '[0-9]*'"],
            capture_output=True, text=True, timeout=25)
        node_ctx = int(unit.stdout.strip()) if unit.returncode == 0 and unit.stdout.strip().isdigit() else None
    except Exception:
        node_ctx = None
    mirrors = {}
    try:
        req = urllib.request.Request("https://api.murakumo.cloud/v1/models",
                                     headers={"User-Agent": "fleet-model-watch/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            v1 = json.load(r)
        for m in v1.get("data", []):
            if m.get("id") == "ling-3.0-tiny":
                mirrors["v1models_context_window"] = m.get("context_window")
        req = urllib.request.Request("https://api.murakumo.cloud/infer/models/ling-3.0-tiny",
                                     headers={"User-Agent": "fleet-model-watch/1.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            mirrors["catalog_context"] = json.load(r).get("context")
    except Exception:
        pass
    if node_ctx is None:
        # unreachable node is NOT measured — refuse to claim mirror agreement
        window_check = {"status": "UNMEASURED", "why": "node unit read failed (ssh)",
                        "mirrors": mirrors}
    else:
        diverged = {k: v for k, v in mirrors.items() if v is not None and v != node_ctx}
        window_check = {"status": "MEASURED", "node_ctx": node_ctx,
                        "mirrors": mirrors,
                        "diverged": diverged or None}
        if diverged:
            fault_sigs["usagi-window-divergence"] = len(diverged)

    entry = {
        "ts": now,
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "window_hours": round(window_h, 2) if window_h else None,
        "per_model": {m: dict(v) for m, v in sorted(per_model.items())},
        "jobs_status_error": drift,
        "fault_signatures": dict(fault_sigs),
    }
    # latency distribution per model (only where measured): p50/max plus a
    # cold-suspect counter so a 150 s success is visible as cold, not failure
    lat_summary = {}
    for m, lats in lat_by_model.items():
        if not lats:
            continue
        s = sorted(lats)
        lat_summary[m] = {
            "n": len(s),
            "p50_s": s[len(s) // 2],
            "max_s": s[-1],
            "cold_suspect": sum(1 for x in s if x >= COLD_SUSPECT_S),
        }
    if lat_summary:
        entry["latency"] = lat_summary
    entry["usagi_window"] = window_check
    with open(LEDGER, "a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # evidence floor: report what was measured, refuse if nothing
    n_runs = sum(v["ok"] + v["fail"] for v in per_model.values())
    print(f"SCANNED\t{n_runs} graded runs, {len(per_model)} models, {drift} jobs in error state")
    if n_runs == 0 and not fault_sigs and since:
        print("no graded runs in window — appending empty window record")
    for m, v in sorted(per_model.items(), key=lambda kv: -(kv[1]["ok"]+kv[1]["fail"])):
        tot = v["ok"] + v["fail"]
        rate = f"{v['ok']*100//tot}%" if tot else "n/a"
        print(f"  {m}\tok={v['ok']}/{tot} ({rate}) in={v['in_tok']:,} out={v['out_tok']:,}")
    if fault_sigs:
        print("FAULTS\t" + json.dumps(dict(fault_sigs)))
    else:
        print("FAULTS\t{}")
    sys.exit(0)

if __name__ == "__main__":
    main()
