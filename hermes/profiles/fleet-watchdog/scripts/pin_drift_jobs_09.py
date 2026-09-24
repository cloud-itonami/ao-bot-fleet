#!/usr/bin/env python3
"""Pin unpinned drift_skip jobs to openrouter-free / z-ai/glm-5.3-flash."""
import os
import subprocess

jobs = [
    ("hakobi", "db9a1f6d0a8b"),
    ("hakobi", "a59179cb36e7"),
    ("legal-disclosure-crawl", "e4fec5bf3fe9"),
    ("murakumo-cloud", "c46baeb5c90a"),
    ("rule-kaizen", "24b4bec8c51b"),
    ("server-operator-crawl", "803bd5efe1c0"),
    ("ubc-growth", "44a071351206"),
    ("webcontainer", "dc39f395b93d"),
    ("whois-org-crawl", "3fc41c5643c0"),
]

HOME_BASE = os.path.expanduser("~/.hermes/profiles")

for home, jid in jobs:
    hermes_home = os.path.join(HOME_BASE, home)
    env = dict(os.environ)
    env["HERMES_HOME"] = hermes_home
    cmd = ["hermes", "cron", "edit", jid,
           "--provider", "openrouter-free", "--model", "z-ai/glm-5.3-flash"]
    try:
        r = subprocess.run(cmd, env=env, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=120, check=False)
        tail = (r.stdout or "").strip().splitlines()
        tail = tail[-3:] if tail else []
        print(f"[{home}] {jid}: rc={r.returncode} last_lines={' | '.join(tail)[:200]}")
    except Exception as e:
        print(f"[{home}] {jid}: EXC {e}")