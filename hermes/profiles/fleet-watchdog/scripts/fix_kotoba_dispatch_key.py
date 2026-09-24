#!/usr/bin/env python3
"""Fix NOENV kotoba-dispatch-followup: create .env with OPENROUTER_API_KEY
copied from the hyakka-crawl canonical source."""
import os

HOME = "~/.hermes"
SRC = f"{HOME}/profiles/hyakka-crawl/.env"
DST_DIR = f"{HOME}/profiles/kotoba-dispatch-followup"
DST = f"{DST_DIR}/.env"

def read_key(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                v = line.split("=", 1)[1]
                if len(v) > 5:
                    return "OPENROUTER_API_KEY=" + v
    return None

key = read_key(SRC)
if not key:
    print("FAIL: no canonical key in", SRC)
    raise SystemExit(1)

os.makedirs(DST_DIR, exist_ok=True)
with open(DST, "w") as f:
    f.write(key + "\n")
print("WROTE", DST)
print("content:", open(DST).read().strip()[:25] + "...")
