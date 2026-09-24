#!/usr/bin/env python3
"""Check every profile .env for OPENROUTER_API_KEY; report missing."""
import glob, os, re

pat = re.compile(r"^OPENROUTER_API_KEY=..*$", re.M)
missing_env, missing_key = [], []
for d in sorted(glob.glob("~/.hermes/profiles/*/")):
    env = os.path.join(d, ".env")
    if not os.path.isfile(env):
        missing_env.append(d)
        continue
    with open(env) as f:
        if not pat.search(f.read()):
            missing_key.append(d)
print("NOENV:", missing_env)
print("NOKEY:", missing_key)
print("counts:", len(missing_env), len(missing_key))
