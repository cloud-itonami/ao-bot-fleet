# ao-bot-fleet

`cloud-itonami/ao-bot-fleet` — resident bots that watch the hermes bot fleet itself.

The fleet's own health: cron runs, model routing, provider capacity, and whether the other bots are doing their work. These bots own no product; their subject is the fleet.

The subject and the bots are one repository: the Hermes profiles that act
here live in [`hermes/profiles/`](hermes/) and are the source of truth for
`~/.hermes/profiles/<profile>` on the host (ADR-2609241200). Secrets, ledgers,
workspace and run state stay on the host.

## Naming

`ao-` is the role prefix for a repository that is a resident bot (the
kotoba-lang/ao artificial-organism model) whose subject and Hermes profile
live together. Identity is the path `cloud-itonami/ao-bot-fleet`.

## Profiles

| profile | role |
|---|---|
| `codinator` | codinator — 他のbotが適切に動いているかをメンテナンス |
| `cron-health` | cron-health: hourly Hermes bot cron fleet health auditor - scans all profiles, detects breaks. propose-only. |
| `fleet-capability-watch` | Capability-model watch for the murakumo fleet: measures serving state |
| `fleet-kaizen` | fleet-kaizen — 品質・安定性・性能の kaizen bot |
| `fleet-model-watch` | Fleet model-assignment health monitor. Measures per-model ok-rate and |
| `fleet-watchdog` | fleet-watchdog |
| `manager` | maanger — 他の bot がちゃんと働いているか確認 |
| `maturity-fleet` | ISIC/ISCO 807 repo の成熟度を毎日観測し最低スコアの1本に1 finding提案する propose-only bot |
