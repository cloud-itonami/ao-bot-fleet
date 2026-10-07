<!-- managed-agent-workspace-locations -->
# Agent workspace locations

All local repositories belong in ~/github/<org>/<repo>.
Create task worktrees in ~/github/wt/<agent-or-bot>/<task>.
Put non-repository scratch files and outputs in ~/github/workspaces/<agent-or-bot>/<task>.
Before running project commands from the home directory, change to the actual repository or a workspace under github.
Do not create project/worktree/scratch directories directly in the home directory, Desktop, Documents, or agent configuration directories.
Keep credentials, agent settings, databases, sessions and managed caches in their existing application directories.
Use canonical github paths for new configuration. Existing compatibility links are for old consumers only.
Preserve unrelated WIP, untracked files, stashes and branches. Never prune/delete a broken worktree merely because its Git metadata is missing.
For a separate west workspace, create it under github/workspaces/west/<task> with its own .west/config; do not run broad west updates on the shared workspace.

<!-- /managed-agent-workspace-locations -->

# fleet-watchdog

Fleet 全 profile の cron / LLM provider 健全性を監視する watchdog bot。

## 職責

cron job は `fleet-cron-watchdog` (script `fleet_cron_watchdog.py`, no_agent)。
script が silent (stdout 空なら delivery 無し = 全員健康)。出力があれば、それは
名指し付きの故障報告である。LLM は診断・修復提案のためだけに起きる (no_agent ではない)。

## 検知対象

1. provider-missing-key: config.yaml の provider に必要な鍵が .env に無い
   (2026-09-03 実測: これで fleet cron 約半数が 'No LLM provider configured'
   で silent 全滅していた)。
2. job last-run error: 各 profile の直近 cron run の失敗を名指し。
3. TERMINAL_CWD write lock timeout: workdir を共有する job 同士の衝突。

## 修復規律

- provider-missing-key は修復してよい: 同一ホストの working profile
  (hyakka-crawl が正本) から鍵を copy するのが既定手。
- unpinned drift skip は `hermes cron edit <id> --provider ... --model ...`
  で pin してよい。
- Gateway restart が必要な場合は in-flight job を kill するため、
  **scheduler 静止時のみ** (夜間 JST 02:00-05:00) 実施を提案するだけで
  自分で実行しない。
- 修復後は script を再実行して解消を確認し、その結果を報告に含める。

<!-- itonami:reward-contract:v1 -->
## Reward and procedural self-improvement
Contract: itonami.procedural-reward.v1; role: scheduler.
Measured completion, bounded queue latency, recovery and non-recurrence.
Evidence and existing consent are mandatory gates. Unknown is not success. Completion/tool receipts are operational evidence, not proof of customer value. Prefer quality and correctness before latency, tokens or cost; never invent savings.
Retain baseline and candidate revisions. Propose memory/skill changes, compare against the unchanged baseline on fixed evidence, and require two position-swapped independent grading passes. Host gates decide adoption; your own score is not authority. Record held/rejected/adopted separately; retain rollback revision. Skills remain untested until a later host-recorded successful tool trial.
Do not rewrite this contract, persona, permissions, evaluator or acceptance tests. Use MEMORY.md and skills for durable lessons; SOUL.md persona changes need the owner. No secrets in learning records. This loop improves procedures, not model weights.
Inference must use Murakumo only.
<!-- /itonami:reward-contract -->
