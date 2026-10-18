#!/usr/bin/env python3
"""global-infra-capacity evidence script (read-only measurement).

Measures world power / CPU / network / storage / GPU industry indicators from
keyless public sources and appends one record per run to the profile ledger.

Sources
  1. Our World in Data grapher CSV (electricity generation, world, TWh)
  2. SEC EDGAR companyconcept revenue (quarterly, USD) as production proxies:
     NVDA (GPU), INTC (CPU), CSCO (network), WDC (storage), MU (memory),
     TSM (foundry/semiconductor manufacturing)

Revenue is a PROXY, not a production volume. Every metric key says so.
Anything not measured is printed as UNMEASURED with a reason and recorded
as such; it is never reported as zero or as success.

Output contract: MEASURE<TAB>key<TAB>value lines, then UNMEASURED<TAB>key<TAB>reason
lines, then one STATUS line. Exit 0 always (a blind run is still a run);
exit 2 only when the ledger itself cannot be written.

This script makes the decisions about WHAT was measured. The agent must not
re-measure or second-guess these numbers; corrections go through a script fix.
"""

import json
import os
import re
import ssl
import sys
import urllib.request
from datetime import datetime, timezone

# macOS system/pyenv pythons often lack a usable CA bundle ("unable to get
# local issuer certificate"). Prefer certifi when importable so the script
# works unattended under the cron runner's interpreter too.
try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # noqa: BLE001 - fall back to the interpreter default
    _SSL_CTX = ssl.create_default_context()

PROFILE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(PROFILE, "workspace", "infra-capacity-ledger.jsonl")
UA = "global-infra-capacity research bot (https://itonami.cloud; read-only public data)"
FETCH_TIMEOUT = 30

OWID_ELEC_URL = (
    "https://ourworldindata.org/grapher/electricity-generation.csv"
    "?v=1&csvType=full&useColumnShortNames=true"
)
EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
EDGAR_CONCEPT_URL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik}/us-gaap/{concept}.json"
)
REVENUE_CONCEPTS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
]

# ticker -> (metric prefix, what it stands for)
PROXIES = {
    "NVDA": ("gpu_proxy_nvidia_revenue_usd", "GPU / accelerator production proxy"),
    "INTC": ("cpu_proxy_intel_revenue_usd", "CPU production proxy"),
    "CSCO": ("network_proxy_cisco_revenue_usd", "network equipment production proxy"),
    "WDC": ("storage_proxy_wdc_revenue_usd", "storage device production proxy"),
    "MU": ("mem_proxy_micron_revenue_usd", "memory / storage production proxy"),
    "TSM": ("fab_proxy_tsmc_revenue_usd", "semiconductor foundry production proxy"),
}


def fetch(url, headers=None):
    hdrs = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT, context=_SSL_CTX) as resp:
            return resp.read()
    except Exception as exc:  # noqa: BLE001 - fall back to curl below
        first_err = exc
    # Last-resort fallback: curl carries the host's CA store and is what the
    # interactive shell proves works. A blind unattended run must not fail
    # just because the cron interpreter has no CA bundle.
    import subprocess

    cmd = ["curl", "-sSL", "--fail", "--max-time", str(FETCH_TIMEOUT)]
    for key, value in hdrs.items():
        cmd += ["-H", "%s: %s" % (key, value)]
    cmd.append(url)
    try:
        out = subprocess.run(cmd, capture_output=True, check=True)
        return out.stdout
    except Exception:  # noqa: BLE001
        raise first_err


def measure_power(metrics, unmeasured):
    raw = fetch(OWID_ELEC_URL).decode("utf-8", "replace")
    lines = raw.strip().splitlines()
    if not lines or not lines[0].lower().startswith("entity"):
        unmeasured["power_world_generation_twh"] = "unexpected CSV header"
        return
    header = [h.strip().lower() for h in lines[0].split(",")]
    val_col = None
    for candidate in ("total_generation__twh", "electricity_generation"):
        if candidate in header:
            val_col = candidate
            break
    try:
        i_entity, i_code, i_year = (
            header.index("entity"),
            header.index("code"),
            header.index("year"),
        )
        i_val = header.index(val_col) if val_col else -1
    except ValueError:
        i_val = -1
    if i_val < 0:
        unmeasured["power_world_generation_twh"] = "CSV columns changed: %s" % ",".join(header)
        return
    world = {}
    for line in lines[1:]:
        cols = line.split(",")
        if len(cols) <= max(i_entity, i_code, i_year, i_val):
            continue
        if cols[i_code] != "OWID_WRL":
            continue
        try:
            world[int(cols[i_year])] = float(cols[i_val])
        except ValueError:
            continue
    if not world:
        unmeasured["power_world_generation_twh"] = "no world rows in CSV"
        return
    latest = max(world)
    metrics["power_world_generation_twh"] = round(world[latest], 1)
    metrics["power_world_generation_year"] = latest
    if latest - 1 in world and world[latest - 1]:
        yoy = (world[latest] / world[latest - 1] - 1.0) * 100.0
        metrics["power_world_generation_yoy_pct"] = round(yoy, 2)


def edgar_cik_map():
    raw = fetch(EDGAR_TICKERS_URL)
    data = json.loads(raw)
    out = {}
    for row in data.values():
        out[row.get("ticker", "").upper()] = str(row.get("cik_str", "")).zfill(10)
    return out


def measure_edgar_proxies(metrics, unmeasured):
    try:
        ciks = edgar_cik_map()
    except Exception as exc:  # noqa: BLE001 - report, never crash the run
        for ticker, (prefix, _what) in PROXIES.items():
            unmeasured[prefix + "_qtr"] = "ticker map fetch failed: %s" % type(exc).__name__
        return
    for ticker, (prefix, _what) in PROXIES.items():
        cik = ciks.get(ticker)
        if not cik:
            unmeasured[prefix + "_qtr"] = "ticker %s not in SEC ticker map" % ticker
            continue
        frames = {}
        for concept in REVENUE_CONCEPTS:
            try:
                raw = fetch(EDGAR_CONCEPT_URL.format(cik=cik, concept=concept))
                data = json.loads(raw)
            except Exception:  # noqa: BLE001 - try next concept
                continue
            usd = (data.get("units") or {}).get("USD") or []
            for entry in usd:
                frame = entry.get("frame") or ""
                m = re.fullmatch(r"CY(\d{4})Q([1-4])", frame)
                if not m:
                    continue
                key = (int(m.group(1)), int(m.group(2)))
                if key in frames:
                    continue  # earlier concept in REVENUE_CONCEPTS wins
                try:
                    frames[key] = float(entry["val"])
                except (KeyError, TypeError, ValueError):
                    continue
        if not frames:
            unmeasured[prefix + "_qtr"] = "no quarterly us-gaap revenue frames on EDGAR"
            continue
        keys = sorted(frames)
        latest = keys[-1]
        metrics[prefix + "_qtr"] = int(frames[latest])
        metrics[prefix + "_qtr_period"] = "CY%dQ%d" % latest
        yoy_key = (latest[0] - 1, latest[1])
        if yoy_key in frames and frames[yoy_key]:
            yoy = (frames[latest] / frames[yoy_key] - 1.0) * 100.0
            metrics[prefix + "_qtr_yoy_pct"] = round(yoy, 2)


def main():
    metrics = {}
    unmeasured = {}
    for step, what in (
        (measure_power, "power"),
        (measure_edgar_proxies, "edgar"),
    ):
        try:
            step(metrics, unmeasured)
        except Exception as exc:  # noqa: BLE001 - one dead source must not kill the run
            unmeasured[what] = "%s: %s" % (type(exc).__name__, exc)

    for key in sorted(metrics):
        print("MEASURE\t%s\t%s" % (key, metrics[key]))
    for key in sorted(unmeasured):
        print("UNMEASURED\t%s\t%s" % (key, unmeasured[key]))

    if not metrics:
        print("REFUSED\tall sources failed; this run measured nothing. do not report success.")
    else:
        print(
            "STATUS\tOK_MEASURED\tmeasured=%d\tunmeasured=%d"
            % (len(metrics), len(unmeasured))
        )

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "schema": "global-infra-capacity.evidence.v1",
        "metrics": metrics,
        "unmeasured": unmeasured,
        "source_of_truth": "scripts/infra_capacity_evidence.py",
    }
    try:
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        if not os.path.exists(LEDGER):
            with open(LEDGER, "w", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": record["ts"],
                            "schema": record["schema"],
                            "bootstrap": True,
                            "note": "append-only ledger. do not edit by hand.",
                        }
                    )
                    + "\n"
                )
        with open(LEDGER, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        print("LEDGER\tappended\t%s" % LEDGER)
    except Exception as exc:  # noqa: BLE001 - a run that cannot record is a failure
        print("LEDGER\tFAILED\t%s: %s" % (type(exc).__name__, exc))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())