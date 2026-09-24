#!/usr/local/bin/python3
"""fleet-kaizen-audit.py - quality/stability/performance kaizen measurement.

no_agent pre-run script: stdout is injected into the agent's prompt as the
measurement for this iteration. Reads ONLY real logs:
  - each profile's cron/executions.db   (quality: status, error strings)
  - each profile's state.db sessions    (stability, performance, cost)
  - fleet-alloc cron-econ-ledger.jsonl  (weekly trend)

Env: KAIZEN_DAYS (default 7), KAIZEN_TOP (default 10).
Propose-only: never edits jobs. Output is the measurement, not the proposal.
"""
import json
import os
import sqlite3
import sys
import time
import collections

PROFILES_DIR = os.path.expanduser("~/.hermes/profiles")
DAYS = int(os.environ.get("KAIZEN_DAYS", "7"))
TOP = int(os.environ.get("KAIZEN_TOP", "10"))
SELF = "fleet-kaizen"


def load_execs():
    """quality: per-profile exec status + error classification."""
    out = {}
    for d in sorted(os.listdir(PROFILES_DIR)):
        if d == SELF or ".bak" in d:
            continue
        edb = os.path.join(PROFILES_DIR, d, "cron", "executions.db")
        if not os.path.exists(edb):
            continue
        try:
            con = sqlite3.connect("file:%s?mode=ro" % edb, uri=True)
            st = dict(con.execute(
                "SELECT status, COUNT(*) FROM executions"
                " WHERE claimed_at > datetime('now', ?) GROUP BY status",
                ("-%d days" % DAYS,)).fetchall())
            errs = con.execute(
                "SELECT substr(COALESCE(error,''),1,90) e, COUNT(*) c"
                " FROM executions WHERE status='failed'"
                " AND claimed_at > datetime('now', ?) AND error IS NOT NULL"
                " GROUP BY e ORDER BY c DESC LIMIT 3",
                ("-%d days" % DAYS,)).fetchall()
            con.close()
            if st:
                out[d] = dict(status=st, top_errors=errs)
        except sqlite3.Error:
            continue
    return out


def load_sessions():
    """stability + performance: token, wall-clock, per profile."""
    out = {}
    for d in sorted(os.listdir(PROFILES_DIR)):
        if d == SELF or ".bak" in d:
            continue
        sd = os.path.join(PROFILES_DIR, d, "state.db")
        if not os.path.exists(sd):
            continue
        try:
            con = sqlite3.connect("file:%s?mode=ro" % sd, uri=True)
            r = con.execute(
                "SELECT COUNT(*), SUM(input_tokens+output_tokens),"
                " SUM(estimated_cost_usd), AVG(api_call_count),"
                " AVG(CASE WHEN ended_at IS NOT NULL AND started_at IS NOT NULL"
                "     THEN ended_at - started_at END)"
                " FROM sessions WHERE source='cron' AND started_at > ?",
                (time.time() - DAYS * 86400,)).fetchone()
            n, tok, cost, calls, wall = r or (0, None, None, None, None)
            con.close()
            if n:
                out[d] = dict(sessions=n, tok=tok or 0, cost=cost or 0.0,
                              avg_calls=round(calls or 0, 1),
                              avg_wall_s=round(wall or 0, 1))
        except sqlite3.Error:
            continue
    return out


def load_trend():
    p = os.path.join(PROFILES_DIR, "fleet-alloc", "workspace", "cron-econ-ledger.jsonl")
    if not os.path.exists(p):
        return []
    lines = open(p).read().strip().splitlines()
    return [json.loads(l) for l in lines[-4:]]


def main():
    execs = load_execs()
    sess = load_sessions()
    trend = load_trend()
    lines = ["# fleet-kaizen measurement (last %dd)" % DAYS,
             "measured-at: %s" % time.strftime("%Y-%m-%dT%H:%M:%S%z"),
             ""]
    # quality axis: worst success rates
    q = []
    for prof, e in execs.items():
        done = e["status"].get("completed", 0)
        fail = e["status"].get("failed", 0)
        if done + fail >= 5:
            q.append((fail / (done + fail), prof, done, fail))
    q.sort(reverse=True)
    lines.append("## quality: worst success rates (min 5 runs)")
    lines.append("profile | success | done/fail | top errors")
    for rate, prof, done, fail in q[:TOP]:
        errs = "; ".join("%s x%d" % (e[:50], c) for e, c in execs[prof]["top_errors"])
        lines.append("%s | %.0f%% | %d/%d | %s" % (prof, 100 * (1 - rate), done, fail, errs))
    # stability axis: recurring error classes
    errclass = collections.Counter()
    for prof, e in execs.items():
        for err, c in e["top_errors"]:
            key = err[:60]
            errclass[key] += c
    lines.append("")
    lines.append("## stability: recurring error classes (fleet-wide)")
    for err, c in errclass.most_common(TOP):
        lines.append("%4d x %s" % (c, err))
    # performance axis: tok/run changes vs cost
    lines.append("")
    lines.append("## performance: top token spend (tok/run where computable)")
    rows = []
    for prof, s in sess.items():
        e = execs.get(prof, {}).get("status", {})
        done = e.get("completed", 0)
        rows.append((s["tok"], prof, s, done))
    rows.sort(reverse=True)
    for tok, prof, s, done in rows[:TOP]:
        tpr = " %s/run" % format(int(tok / done), ",") if done else " (no completed runs)"
        lines.append("%s | %s tok | $%.2f | avg wall %.0fs |%s"
                     % (prof, format(int(tok), ","), s["cost"], s["avg_wall_s"], tpr))
    # trend
    if trend:
        lines.append("")
        lines.append("## weekly trend (fleet-alloc ledger)")
        for t in trend:
            lines.append("%s: %s tok, $%.2f" % (
                time.strftime("%Y-%m-%d", time.localtime(t["ts"])),
                format(t["total_tok"], ","), t["cost"]))
    print("\n".join(lines))
    # append-only evidence ledger
    led = os.path.join(PROFILES_DIR, SELF, "workspace", "kaizen-ledger.jsonl")
    os.makedirs(os.path.dirname(led), exist_ok=True)
    with open(led, "a") as fh:
        fh.write(json.dumps(dict(ts=time.time(), days=DAYS,
                                 profiles_quality=len(q),
                                 profiles_perf=len(sess),
                                 top_quality=[[p, round(1 - r, 3), d, f] for r, p, d, f in q[:5]],
                                 top_tok=[[p, int(t)] for t, p, s, d in rows[:5]])) + "\n")


if __name__ == "__main__":
    sys.exit(main())
