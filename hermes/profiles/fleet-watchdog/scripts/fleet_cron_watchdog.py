#!/usr/bin/env python3
"""Fleet cron watchdog — silent-healthy / named-failure report.

Scans every profile under ~/.hermes/profiles/ plus the default home:
  1. LLM provider sanity: config.yaml uses provider X but the required
     key env is absent from .env  -> "provider-missing-key" (the silent
     fleet-killer found 2026-09-03).
  2. Cron last-run status: any job whose last run errored -> named
     with profile, job name, and a one-line reason.
Exit/output discipline: prints NOTHING when fully healthy (watchdog
pattern), otherwise prints a compact report. Deterministic output except
timestamps are trimmed; state only changes when fleet state changes.
"""
from __future__ import annotations

import re
from pathlib import Path

HERMES_ROOT = Path.home() / ".hermes"
PROFILES_DIR = HERMES_ROOT / "profiles"

# provider -> required env var(s)
REQUIRED_KEYS = {
    "openrouter": ["OPENROUTER_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "fireworks": ["FIREWORKS_API_KEY"],
    "zai": ["GLM_API_KEY"],
    "kimi-coding": ["KIMI_API_KEY"],
    "minimax": ["MINIMAX_API_KEY"],
    "gemini": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
}


def profile_homes() -> list[tuple[str, Path]]:
    homes = [("default", HERMES_ROOT)]
    if PROFILES_DIR.is_dir():
        for d in sorted(PROFILES_DIR.iterdir()):
            if d.is_dir() and (d / "config.yaml").is_file():
                homes.append((d.name, d))
    return homes


def provider_of(config_text: str) -> str | None:
    m = re.search(r"^model:\n(?:.*\n)*?\s+provider:\s*(\S+)", config_text, re.M)
    return m.group(1) if m else None


def check_provider_key(name: str, home: Path) -> list[str]:
    problems = []
    cfg = home / "config.yaml"
    env = home / ".env"
    try:
        config_text = cfg.read_text(errors="replace")
    except OSError:
        return []
    provider = provider_of(config_text)
    if not provider or provider not in REQUIRED_KEYS:
        return []
    env_names = REQUIRED_KEYS[provider]
    env_text = env.read_text(errors="replace") if env.is_file() else ""
    # fall back to default profile's .env (shared key pattern)
    default_env = (HERMES_ROOT / ".env")
    default_text = default_env.read_text(errors="replace") if default_env.is_file() else ""
    if not any(re.search(rf"^{v}=", env_text, re.M) for v in env_names) and \
       not any(re.search(rf"^{v}=", default_text, re.M) for v in env_names):
        problems.append(f"{name}: provider-missing-key provider={provider} needs={'/'.join(env_names)} (cron bots would die with 'No LLM provider configured')")
    return problems


def check_last_runs(name: str, home: Path) -> list[str]:
    """Read cron state directly from state.db via hermes CLI output is slow;
    instead parse the cron DB if present. Cheapest reliable probe: the
    gateway log's per-tick lines. We use the CLI as source of truth but
    only for profiles that HAVE cron dirs."""
    problems = []
    cron_dir = home / "cron"
    if not cron_dir.is_dir():
        return problems
    return problems  # filled below in main via subprocess batch


def main() -> int:
    import os
    import subprocess

    problems: list[str] = []
    homes = profile_homes()

    for name, home in homes:
        problems += check_provider_key(name, home)

    # cron last-run sweep: run `hermes cron list` per profile that has cron jobs
    env = dict(os.environ)
    for name, home in homes:
        if not (home / "cron").is_dir():
            continue
        e = dict(env)
        e["HERMES_HOME"] = str(home)
        try:
            out = subprocess.run(
                ["hermes", "cron", "list"], env=e, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                timeout=60, check=False,
            ).stdout
        except (OSError, subprocess.TimeoutExpired):
            problems.append(f"{name}: cron-list-probe timeout/failed")
            continue
        for block in re.split(r"\n  (?=\w{12} \[)", out):
            m = re.search(r"Name:\s+(.+)", block)
            if not m:
                continue
            job = m.group(1).strip()
            last = re.search(r"Last run:\s+(.+)", block)
            if not last:
                continue
            reason = last.group(1).strip()
            if "error:" in reason.lower():
                short = reason.split("error:", 1)[1].strip()[:120]
                problems.append(f"{name}: job '{job}' last-run error: {short}")

    if not problems:
        return 0  # silent = healthy

    print(f"FLEET_CRON_WATCHDOG {len(problems)} problem(s):")
    for p in problems:
        print(f"  - {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
