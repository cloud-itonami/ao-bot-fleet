#!/usr/bin/env python3
"""Pin 10 unpinned drift_skip jobs to current global default
(openrouter-free / deepseek/deepseek-v4-flash-0731) via HERMES_HOME.
Uses full 12-char job id."""
import subprocess, os

PINS = [
    # (HERMES_HOME, full_id, name)
    ("~/.hermes/profiles/design-audit", "62204614f8fa", "design-audit-weekly"),
    ("~/.hermes/profiles/isekai-x402", "c0f24f402770", "x402-price-diff-daily"),
    ("~/.hermes/profiles/oppai-gen", "f288d9331267", "oppai-report"),
    ("~/.hermes/profiles/murakumo-tok", "d08b199efa22", "murakumo-tok-tick"),
    ("~/.hermes/profiles/oriru", "c56107d6ad5f", "oriru-application-pulse"),
    ("~/.hermes/profiles/samu", "076b0d288cbf", "samu-blueprint-registry-watch"),
    ("~/.hermes/profiles/seiri", "312f602e1569", "seiri-cleanup-retirement-weekly"),
    ("~/.hermes/profiles/seiri", "29cfd33c0076", "seiri-weekly-audit"),
    ("~/.hermes/profiles/tobari", "17207ee36d78", "tobari-weekly-standup"),
    ("~/.hermes/profiles/tsuushin", "c9c30f472c4d", "tsuushin-daily"),
]

PROVIDER = "openrouter-free"
MODEL = "deepseek/deepseek-v4-flash-0731"

for home, jid, name in PINS:
    env = dict(os.environ)
    env["HERMES_HOME"] = home
    cmd = ["hermes", "cron", "edit", jid,
           "--provider", PROVIDER, "--model", MODEL]
    try:
        r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)
        ok = "error" not in (r.stdout + r.stderr).lower() or "pin" in (r.stdout.lower())
        print(f"[{'OK ' if r.returncode == 0 else 'ERR'}] {home.split('/')[-1]}/{name} ({jid}) rc={r.returncode}")
        if r.returncode != 0:
            print("     stderr:", (r.stderr or r.stdout)[-300:].strip())
    except Exception as e:
        print(f"[EXC] {name}: {e}")