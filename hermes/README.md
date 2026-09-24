# hermes/ — the resident bots that act for this repository

This directory is the **source of truth** for the Hermes profiles listed below
(ADR-2609241200). The host's `~/.hermes/profiles/<profile>` is materialized
from `hermes/profiles/<profile>/` and checked against it:

```
kbb --backend sci scripts/hermes-profile-repo.cljk materialize <profile>   # repo -> host
kbb --backend sci scripts/hermes-profile-repo.cljk check <profile>         # 0 agree / 1 drift / 2 could not compare
kbb --backend sci scripts/hermes-profile-repo.cljk export <profile>        # host -> repo, then commit
```

(run from the com-junkawasaki/root superproject; registry
`manifest/hermes-profile-repos.edn`.)

Each profile directory holds SOUL.md, profile.yaml, config.yaml (host-local
blocks removed), cron/jobs.json (definitions only), scripts/ and the skills the
profile owns. **Never here:** `.env` or any secret value, workspace/ledgers,
sessions, memories, logs, caches, run state.

## Profiles

| profile | description |
|---|---|
| `codinator` | codinator — 他のbotが適切に動いているかをメンテナンス |
| `cron-health` | cron-health: hourly Hermes bot cron fleet health auditor - scans all profiles, detects breaks. propose-only. |
| `fleet-capability-watch` | Capability-model watch for the murakumo fleet: measures serving state |
| `fleet-kaizen` |  |
| `fleet-model-watch` | Fleet model-assignment health monitor. Measures per-model ok-rate and |
| `fleet-watchdog` |  |
| `manager` | maanger — 他の bot がちゃんと働いているか確認 |
| `maturity-fleet` | ISIC/ISCO 807 repo の成熟度を毎日観測し最低スコアの1本に1 finding提案する propose-only bot |
