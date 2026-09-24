#!/usr/bin/env python3
"""Capability-model watch for the murakumo fleet -- decision-free measurement.

Two faces, measured fresh every tick, appended to an append-only ledger:
  1. murakumo gateway faces (live):
     - GET /v1/models            -> the serve face (what callers can name)
     - GET /infer/models         -> the catalog face (modality/status/freshness)
     - GET /infer/nodes          -> edge ring (best effort; may time out)
  2. huggingface availability of the 32GB-tier candidate list (this script's
     WATCHLIST) -- repo exists (200 vs 404/401) + trailing-30d downloads.

Exit codes: 0 measured and appended / 2 REFUSED (could not measure).
--no-agent script job: spends zero model tokens.
"""
import json, os, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "capability-watch-ledger.jsonl")
BASE = "https://api.murakumo.cloud"

# Candidate repos per capability (measured 2026-09-14 research tick; scores are
# third-party/self-reported benchmark numbers, not fleet measurements).
# "pin" marks the tier-1 pick this fleet would onboard first.
WATCHLIST = {
    "cua": [
        {"repo": "Hcompany/Holo-3.1-35B-A3B-GGUF", "pin": True,
         "score": "OSWorld-V 74.2% self-reported (BF16), quant -2pt",
         "size": "q4_k_m 21.3GB + mmproj 0.9GB"},
        {"repo": "bartowski/tencent_UI-Mate-27B-GGUF", "pin": True,
         "score": "OSWorld-V 77.0% (vendor self-report)",
         "size": "IQ4_XS 15.3GB / Q4_K_M 17.5GB + mmproj 0.93GB"},
        {"repo": "tencent/UI-Mate-27B", "pin": False,
         "score": "OSWorld-V 77.0% (BF16 weights, ~54GB)", "size": "bf16 only"},
        {"repo": "mPLUG/GUI-Owl-1.5-32B-Instruct", "pin": False,
         "score": "OSWorld-V 56.5% (Instruct)", "size": "bf16 only"},
    ],
    "image": [
        {"repo": "Tongyi-MAI/Z-Image-Turbo", "pin": True,
         "score": "8-step turbo, 16GB VRAM class, Apache-2.0",
         "size": "6B turbo (GGUF available: jayn7)"},
        {"repo": "black-forest-labs/FLUX.2-klein-4B", "pin": True,
         "score": "FLUX.2 small tier, ~13GB class", "size": "4B bf16/fp8"},
        {"repo": "Qwen/Qwen-Image", "pin": False,
         "score": "best open text rendering, 20B (GGUF quantized community)",
         "size": "bf16 only official"},
    ],
    "video": [
        {"repo": "QuantStack/Wan2.2-TI2V-5B-GGUF", "pin": True,
         "score": "TI2V 5B, 720p, 8GB VRAM class (GGUF), Apache-2.0",
         "size": "5B GGUF multiple quants"},
        {"repo": "QuantStack/Wan2.2-T2V-A14B-GGUF", "pin": False,
         "score": "A14B MoE, 12GB-class GGUF, higher quality",
         "size": "A14B GGUF multiple quants"},
    ],
    "music": [
        {"repo": "ACE-Step/Ace-Step1.5", "pin": True,
         "score": "2B base / 4B XL (12GB class with offload), <4GB VRAM base",
         "size": "2B + XL 4B variants"},
        {"repo": "ResembleAI/chatterbox", "pin": False,
         "score": "Elo 1020, MIT, 0.5B -- closest open Suno-line w/ vocals",
         "size": "0.5B"},
    ],
    "tts": [
        {"repo": "hexgrad/Kokoro-82M", "pin": True,
         "score": "Elo 1060, 82M, Apache-2.0, <2GB VRAM, no cloning",
         "size": "82M"},
        {"repo": "ResembleAI/chatterbox", "pin": True,
         "score": "Elo 1020, cloning + emotion, MIT", "size": "0.5B"},
    ],
    "vision": [
        {"repo": "Qwen/Qwen3-VL-8B-Instruct-GGUF", "pin": True,
         "score": "MMMU 62.3 (8B class), native 256K ctx",
         "size": "Q4_K_M 5.03GB + mmproj 1.16GB (official)"},
        {"repo": "Qwen/Qwen3-VL-8B-Thinking-GGUF", "pin": False,
         "score": "MMMU 58.2 thinking variant", "size": "same family"},
    ],
}

UA = {"User-Agent": "itonami-capability-watch (fleet capability model watch)"}


def refuse(why):
    print("REFUSED -- ledger not appended.")
    print(why)
    sys.exit(2)


def get(url, timeout=15, auth=None):
    headers = dict(UA)
    if auth:
        headers["authorization"] = f"Bearer {auth}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


def murakumo_faces(key):
    faces = {}
    # /v1/models: serve face. Non-200 or unparseable = unmeasured (do not
    # record an empty list as if the gateway serves nothing).
    try:
        s, b = get(BASE + "/v1/models", auth=key)
        j = json.loads(b)
        faces["serve_ids"] = sorted(m.get("id", "") for m in j.get("data", []))
        faces["serve_count"] = len(faces["serve_ids"])
    except Exception as e:
        faces["serve_error"] = f"{type(e).__name__}: {e}"[:120]
    # /infer/models: catalog face (list form)
    try:
        s, b = get(BASE + "/infer/models", auth=key)
        j = json.loads(b)
        faces["catalog"] = [
            {"id": m.get("id"), "modality": m.get("modality"),
             "status": m.get("status"),
             "fresh": ((m.get("status-evidence") or {}).get("verdict")),
             "fleet": m.get("fleet")}
            for m in j if isinstance(m, dict)]
    except Exception as e:
        faces["catalog_error"] = f"{type(e).__name__}: {e}"[:120]
    # /infer/nodes: best effort, may be slow
    try:
        s, b = get(BASE + "/infer/nodes", auth=key, timeout=25)
        faces["nodes_bytes"] = len(b)
    except Exception as e:
        faces["nodes_error"] = f"{type(e).__name__}: {e}"[:120]
    return faces


def hf_probe(repo):
    """Return (state, downloads). 401/404 = gated/not-found -- neither is
    'absent evidence'; both are recorded as states, not as 0."""
    url = f"https://huggingface.co/api/models/{repo}"
    try:
        s, b = get(url)
        j = json.loads(b)
        return "ok", j.get("downloads")
    except urllib.error.HTTPError as e:
        return f"http{e.code}", None
    except Exception as e:
        return f"err:{type(e).__name__}", None


def main():
    key = (os.environ.get("MURAKUMO_API_KEY")
           or os.environ.get("MURAKUMO_API_TOKEN"))
    try:
        for line in open(os.path.join(os.path.dirname(HERE), ".env")):
            line = line.strip()
            if line.startswith("MURAKUMO_API_KEY="):
                key = line.split("=", 1)[1]
    except FileNotFoundError:
        pass
    if not key:
        refuse("no MURAKUMO_API_KEY in env or profile .env")

    faces = murakumo_faces(key)
    if "serve_error" in faces and "catalog_error" in faces:
        refuse(f"gateway unreachable on both faces: {faces}")

    watch = {}
    for cap, entries in WATCHLIST.items():
        watch[cap] = []
        for e in entries:
            state, dl = hf_probe(e["repo"])
            watch[cap].append({**e, "hf_state": state, "downloads_30d": dl,
                               "measured_at": time.strftime("%Y-%m-%d", time.gmtime())})

    rec = {"ts": time.time(), "as_of": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "faces": faces, "watchlist": watch}
    with open(LEDGER, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"MEASURE\tserve_count\t{faces.get('serve_count', 'unmeasured')}")
    print(f"MEASURE\tserve_ids\t{','.join(faces.get('serve_ids', [])) or 'unmeasured'}")
    cat = faces.get("catalog")
    if cat is None:
        print("MEASURE\tcatalog\tunmeasured")
    else:
        mods = sorted({str(m.get('modality')) for m in cat})
        print(f"MEASURE\tcatalog_entries\t{len(cat)}")
        print(f"MEASURE\tcatalog_modalities\t{','.join(mods)}")
        print(f"MEASURE\tcatalog_modalities\t{','.join(m['id'] + ':' + str(m.get('modality')) + ':' + str(m.get('status')) for m in cat)}")
    for cap, entries in watch.items():
        for e in entries:
            print(f"MEASURE\t{cap}\t{e['repo']}\t{e['hf_state']}\t{e['downloads_30d']}")
    print("appended to", LEDGER)


if __name__ == "__main__":
    main()
