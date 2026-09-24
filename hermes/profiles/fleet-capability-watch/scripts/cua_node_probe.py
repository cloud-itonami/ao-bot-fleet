#!/usr/bin/env python3
"""CUA node probe -- UI-Mate-27B IQ4_XS on gad (Ryzen AI Max+ 395).

Decision-free measurement of the tier-1 CUA pick on its actual node, via SSH.
One tick = one node, one probe cycle:
  1. start llama-server on port 8093 with the pinned GGUFs (if not already up)
  2. text step-JSON generation probe (GUI-agent shaped, ~70 output tokens) x3
  3. server-side timings -> gen tok/s (decode) + prompt tok/s (prefill)
  4. append ledger row + stop the probe server (fleet services 8090/8091 untouched)

Exit codes: 0 measured / 2 REFUSED (nothing measured -- no fake rows).
Zero model tokens spent (pure subprocess/HTTP probe).
"""
import json, os, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "cua-node-probe-ledger.jsonl")
NODE = os.environ.get("CUA_PROBE_SSH", "gad@100.82.98.110")
PORT = "8093"
MODEL = "/home/gad/models/ui-mate-27b/IQ4_XS.gguf"
MMPROJ = "/home/gad/models/ui-mate-27b/mmproj.gguf"
SERVER = "/home/gad/murakumo/llama.cpp/build-vulkan/llama-b9873/llama-server"
PIN_SHA = {
    "IQ4_XS.gguf": "109f07983d6e14a53f498a9d771645207683983b3ce830331dd84f949355200c",
    "mmproj.gguf": "991376d8e954dda92b454358306fb2b4bbd51d522b12977cdfeb3eebbb904fbb",
}

STEP_PROMPT = (
    "You are a GUI agent. Current screen: itonami.cloud dashboard. Visible: "
    "sidebar (Dashboard, Actors, Wiki, Settings), main area has a button "
    "labeled 新規アクター作成. Task: create a new actor. Output the next single "
    "action as strict JSON {\"thought\":string,\"action\":\"click\"|\"type\"|"
    "\"scroll\"|\"done\",\"target\":string,\"text\":string}. Output only the JSON object."
)


def ssh(cmd, timeout=90):
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", NODE, cmd],
        capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"ssh rc={r.returncode}: {r.stderr.strip()[:200]}")
    return r.stdout


def refuse(why):
    print("REFUSED -- ledger not appended.")
    print(why)
    sys.exit(2)


def main():
    # 1. weights pin check (byte count alone does not catch truncation)
    try:
        out = ssh("sha256sum %s %s" % (MODEL, MMPROJ), timeout=120)
    except Exception as e:
        refuse(f"cannot hash weights on node: {e}")
    got = dict(line.split()[::-1] for line in out.strip().splitlines())
    for fname, want in PIN_SHA.items():
        path = os.path.join(os.path.dirname(MODEL), fname)
        if got.get(path) != want:
            refuse(f"sha256 mismatch for {path}: {got.get(path)} != {want}")

    # 2. ensure probe server up
    try:
        up = ssh(f"curl -s -m 3 http://127.0.0.1:{PORT}/health || true", timeout=30)
    except Exception as e:
        refuse(f"health check failed: {e}")
    started_here = False
    if '"ok"' not in up:
        try:
            ssh(f"nohup {SERVER} -m {MODEL} --mmproj {MMPROJ} -ngl 999 -c 2048 "
                f"--parallel 1 -fa on --host 0.0.0.0 --port {PORT} --jinja "
                f"--reasoning off --alias ui-mate-27b-iq4xs "
                f"> /home/gad/models/ui-mate-27b/probe-serve.log 2>&1 & echo started",
                timeout=30)
            started_here = True
        except Exception as e:
            refuse(f"cannot start probe server: {e}")
        deadline = time.time() + 240
        ok = False
        while time.time() < deadline:
            try:
                up = ssh(f"curl -s -m 3 http://127.0.0.1:{PORT}/health || true", timeout=30)
                if '"ok"' in up:
                    ok = True
                    break
            except Exception:
                pass
            time.sleep(10)
        if not ok:
            refuse("probe server did not become healthy in 240s")

    # 3. probes x3
    runs = []
    body = json.dumps({"model": "ui-mate-27b-iq4xs", "stream": False,
                       "max_tokens": 150,
                       "messages": [{"role": "user", "content": STEP_PROMPT}]})
    for i in range(3):
        t0 = time.time()
        req = urllib.request.Request(
            f"http://127.0.0.1:{PORT}/v1/chat/completions".replace("127.0.0.1", NODE.split("@")[1]),
            data=body.encode(), headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=280) as r:
                j = json.load(r)
        except Exception as e:
            runs.append({"run": i + 1, "error": f"{type(e).__name__}: {e}"[:120]})
            continue
        tm = j.get("timings") or {}
        runs.append({"run": i + 1, "wall_s": round(time.time() - t0, 2),
                     "http": 200, "finish": j["choices"][0].get("finish_reason"),
                     "content_ok": j["choices"][0]["message"]["content"].strip().startswith("{"),
                     "prompt_n": tm.get("prompt_n"),
                     "prompt_tok_s": round(tm.get("prompt_per_second") or 0, 1),
                     "gen_tok_s": round(tm.get("predicted_per_second") or 0, 2),
                     "served_model": j.get("model")})

    # 4. stop probe server only if we started it
    if started_here:
        try:
            ssh(f"pkill -f 'port {PORT}' || true", timeout=30)
        except Exception:
            pass

    good = [r for r in runs if r.get("http") == 200]
    if not good:
        refuse(f"all probe runs failed: {runs}")

    gens = sorted(r["gen_tok_s"] for r in good)
    rec = {"ts": time.time(),
           "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "node": NODE, "model": "ui-mate-27b-iq4xs",
           "quant": "IQ4_XS", "weights_sha256_ok": True,
           "runs": runs,
           "gen_tok_s_min": gens[0], "gen_tok_s_max": gens[-1],
           "server_started_here": started_here}
    with open(LEDGER, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"MEASURE\tcua_node_probe\t{NODE}\truns_ok\t{len(good)}/3")
    for r in good:
        print(f"MEASURE\trun{r['run']}\tgen_tok_s={r['gen_tok_s']}\t"
              f"prompt_tok_s={r['prompt_tok_s']}\tstep_wall_s={r['wall_s']}\t"
              f"json_ok={r['content_ok']}")
    print("appended to", LEDGER)


if __name__ == "__main__":
    main()
