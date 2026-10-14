#!/usr/bin/env python3
"""accountability_evidence.py - ADR-2610081200 rollout evidence.

Read-only measurement of how far the accountability-tiered anonymity
rollout has got, from each repository's remote `main` (git show / git grep;
no network, no checkout, no writes except the append-only ledger).

The agent never recomputes this. Prints SMOKE-OK as the last line only if
every repository could be read; otherwise SMOKE-FAIL and a non-zero exit.

Usage:
  accountability_evidence.py [--root DIR] [--ledger FILE] [--no-ledger]

Env: none (paths derive from HOME unless overridden).
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

REPOS = {
    "protocol": "kotoba-lang/kotoba-protocol",
    "adr": "kotoba-lang/kotoba",
    "messenger": "kotoba-lang/kotobase-messenger",
    "server": "kotoba-lang/kotoba-server",
}

ADR_PATH = "docs/ADR-accountability-tiered-anonymity.md"
PROTO = "src/kotoba/protocol/"

# phase -> list of (label, repo, kind, arg) ; kind: file | grep (any non-doc,
# non-test file in the repo, case-insensitive fixed string)
PHASES = [
    ("R0", [("tier vocabulary + policy/profile schema", "protocol", "file", PROTO + "accountability.cljk"),
            ("govern tier check", "protocol", "grep", "accountability/decide")]),
    ("R1", [("pairwise DIDs", "protocol", "file", PROTO + "pairwise.cljk"),
            ("policy composition", "protocol", "grep", "compose-policies"),
            ("receipt visibility rule", "protocol", "grep", "receipt-visibility"),
            ("messenger mailbox id", "messenger", "grep", "mailbox-id"),
            ("server owner-only receipts", "server", "grep", "OwnerOnly")]),
    ("R2", [("rate-limit token algebra", "protocol", "file", PROTO + "ratelimit.cljk"),
            ("blind-signature issuer/verifier implementation", "server", "grep", "blind_rsa"),
            ("gateway token check", "server", "grep", "ratelimit_token")]),
    ("R3", [("BBS+ credentials", "protocol", "grep", "bbs"),
            ("context nullifier", "protocol", "grep", "nullifier")]),
    ("R4", [("RLN", "protocol", "grep", "rln"),
            ("anonymous stake", "protocol", "grep", "forfeit")]),
    ("R5", [("threshold escrow opening", "protocol", "grep", "threshold-escrow-open"),
            ("transparency log", "protocol", "grep", "transparency-log"),
            ("message franking", "messenger", "grep", "franking")]),
]


def git(repo, *args):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return p.returncode, p.stdout


def main_ref(repo):
    rc, out = git(repo, "for-each-ref", "--format=%(refname:short)", "refs/remotes/*/main")
    refs = [r for r in out.split() if rc == 0]
    if not refs:
        return None
    return "origin/main" if "origin/main" in refs else sorted(refs)[0]


def has_file(repo, ref, path):
    return git(repo, "cat-file", "-e", f"{ref}:{path}")[0] == 0


def has_grep(repo, ref, needle):
    """Implementation evidence only: docs and tests mentioning a name do not
    count (a sentence in a doc is not an implementation)."""
    rc, _ = git(repo, "grep", "-qiF", needle, ref, "--", ".",
                ":(exclude)docs", ":(exclude)*.md", ":(exclude)test", ":(exclude)*/tests/*",
                ":(exclude)*_test.*")
    return rc == 0


def read_file(repo, ref, path):
    rc, out = git(repo, "show", f"{ref}:{path}")
    return out if rc == 0 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/github"))
    ap.add_argument("--ledger", default=os.path.expanduser(
        "~/.hermes/profiles/accountability-steward/workspace/ledger.jsonl"))
    ap.add_argument("--no-ledger", action="store_true")
    a = ap.parse_args()

    ctx, problems = {}, []
    for key, path in REPOS.items():
        repo = os.path.join(a.root, path)
        ref = main_ref(repo) if os.path.isdir(repo) else None
        if ref is None:
            problems.append(f"cannot read {path} (no checkout or no remote main)")
            continue
        ctx[key] = (repo, ref)
        rc, d = git(repo, "log", "-1", "--format=%cs", ref)
        print(f"repo {path:34s} {ref:16s} last-commit {d.strip()}")

    out = {"phases": {}, "drift": [], "adr": None}

    if "adr" in ctx:
        repo, ref = ctx["adr"]
        out["adr"] = has_file(repo, ref, ADR_PATH)
        print(f"adr  {ADR_PATH}: {'present' if out['adr'] else 'MISSING on main'}")

    print("--- phases")
    for name, checks in PHASES:
        done, missing = [], []
        for label, rk, kind, arg in checks:
            if rk not in ctx:
                missing.append(f"{label} (repo unreadable)")
                continue
            repo, ref = ctx[rk]
            ok = has_file(repo, ref, arg) if kind == "file" else has_grep(repo, ref, arg)
            (done if ok else missing).append(label)
        status = "done" if not missing else ("partial" if done else "open")
        out["phases"][name] = {"status": status, "done": done, "missing": missing}
        print(f"{name}: {status}")
        for m in missing:
            print(f"     missing: {m}")

    print("--- drift")
    if "protocol" in ctx:
        repo, ref = ctx["protocol"]
        src = read_file(repo, ref, PROTO + "accountability.cljk") or ""
        m = re.search(r"\(def invariants(.*?)\n\n\(def ", src, re.S)
        declared = set(re.findall(r":l0/[a-z0-9-]+", m.group(1))) if m else set()
        rc, grep_out = git(repo, "grep", "-hoE", r":l0/[a-z0-9-]+", ref, "--", "src", "test")
        used = set(grep_out.split()) if rc == 0 else set()
        undeclared = sorted(used - declared)
        if not declared:
            out["drift"].append("L0 `invariants` map not found in accountability.cljk")
        for u in undeclared:
            out["drift"].append(f"{u} is referenced but not declared in `invariants`")
        rc, stale = git(repo, "grep", "-l", "kotoba-auth", ref, "--", "src", "docs")
        for line in stale.split():
            out["drift"].append(f"retired `kotoba-auth` still referenced in {line.split(':', 1)[-1]}")
    for d in out["drift"]:
        print(f"drift: {d}")
    if not out["drift"]:
        print("drift: none")

    order = ["R0", "R1", "R2", "R3", "R4", "R5"]
    nxt = next((p for p in order if out["phases"].get(p, {}).get("status") != "done"), None)
    print(f"--- next open phase: {nxt}")

    row = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "adr_on_main": out["adr"],
           "phases": {k: v["status"] for k, v in out["phases"].items()},
           "drift": len(out["drift"]), "next": nxt, "problems": problems}
    seq = 0
    if not a.no_ledger:
        os.makedirs(os.path.dirname(a.ledger), exist_ok=True)
        if os.path.exists(a.ledger):
            with open(a.ledger) as f:
                seq = sum(1 for _ in f)
        with open(a.ledger, "a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        seq += 1
    print(f"ledger seq: {seq if not a.no_ledger else 'not written'}")

    if problems:
        for p in problems:
            print(f"SMOKE-FAIL: {p}")
        return 1
    print("SMOKE-OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
