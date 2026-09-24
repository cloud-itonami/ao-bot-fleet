#!/usr/bin/env python3
import os, glob

# Replicates watchdog's check_provider_key incl. default .env fallback:
# a profile is OK if its own .env has OPENROUTER_API_KEY OR if default home .env does.
HOME = "~/.hermes"

def has_key(path):
    if not os.path.exists(path):
        return None  # no env file
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY=") and len(line.split("=",1)[1]) > 5:
                return True
    return False

default_env = f"{HOME}/.env"
default_ok = has_key(default_env)

missing = []
for d in sorted(glob.glob(f"{HOME}/profiles/*")):
    if not os.path.isdir(d):
        continue
    name = os.path.basename(d)
    env = f"{d}/.env"
    k = has_key(env)
    if k is False:
        # no key in profile env; fallback to default if it exists
        if default_ok and os.path.exists(default_env):
            continue  # rescued by fallback
        missing.append((name, "NOKEY"))
    elif k is None:
        missing.append((name, "NOENV"))

using_own = []
for d in sorted(glob.glob(f"{HOME}/profiles/*")):
    name = os.path.basename(d)
    if has_key(f"{d}/.env") is True:
        using_own.append(name)

print("default .env has key:", bool(default_ok and os.path.exists(default_env)))
print("profiles with own key:", len(using_own))
print("MISSING (after fallback):", len(missing))
for m in missing:
    print("  ", m)