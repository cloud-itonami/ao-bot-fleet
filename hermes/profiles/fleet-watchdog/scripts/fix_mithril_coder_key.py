#!/usr/bin/env python3
"""Fix NOENV for mithril-coder-openrouter: create .env from hyakka-crawl key (2026-09-23)."""
import os
src = os.path.expanduser("~/.hermes/profiles/hyakka-crawl/.env")
dst_home = os.path.expanduser("~/.hermes/profiles/mithril-coder-openrouter")
os.makedirs(dst_home, exist_ok=True)
dst = os.path.join(dst_home, ".env")
key = None
with open(src) as f:
    for line in f:
        if line.startswith("OPENROUTER_API_KEY=") and len(line.split("=",1)[1].strip()) > 5:
            key = line.strip()
            break
assert key, "source key not found"
with open(dst, "w") as f:
    f.write(key + "\n")
print("CREATED", dst)
