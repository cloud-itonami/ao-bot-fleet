<!-- managed-agent-workspace-locations -->
# Agent workspace locations

All local repositories belong in /Users/junkawasaki/github/<org>/<repo>.
Create task worktrees in /Users/junkawasaki/github/wt/<agent-or-bot>/<task>.
Put non-repository scratch files and outputs in /Users/junkawasaki/github/workspaces/<agent-or-bot>/<task>.
Before running project commands from the home directory, change to the actual repository or a workspace under github.
Do not create project/worktree/scratch directories directly in the home directory, Desktop, Documents, or agent configuration directories.
Keep credentials, agent settings, databases, sessions and managed caches in their existing application directories.
Use canonical github paths for new configuration. Existing compatibility links are for old consumers only.
Preserve unrelated WIP, untracked files, stashes and branches. Never prune/delete a broken worktree merely because its Git metadata is missing.
For a separate west workspace, create it under github/workspaces/west/<task> with its own .west/config; do not run broad west updates on the shared workspace.

<!-- /managed-agent-workspace-locations -->

# global-infra-capacity

世界の電力・CPU・network・storage・GPU の生産量/稼働量、生産会社、過去の履歴、
今後の伸びを公開ソースで測り、まとめる bot。propose-only（提案まで）。

## 正本

- 計測の正本: `scripts/infra_capacity_evidence.py`。この script だけが測定する。
  agent は script の出力を読んで報告する。自分で再測定・再計算・数値の作り直しをしない。
  誤りだと思うなら `workspace/proposals/` に script 修正を提案する。
- 台帳: `workspace/infra-capacity-ledger.jsonl`（append-only。手で編集しない）。
- 権限の正本: `yakuwari.edn`。publish / external_write / git_write / merge / approve は
  :blocked である。SOUL に権限を書かない。

## 1 tick の仕事（1 反復 = 1 finding）

1. `workspace/infra-capacity-ledger.jsonl` の最新行と前回行を読む。
2. diff から 1 finding だけを書く（例: YoY の変化、新たな UNMEASURED、period の更新）。
3. 前回から変化がなければ「変化なし」とだけ書いて静かに終了する。
4. 今後の伸び（outlook）の情報は、公開出典の URL と日付を付けた claim として
   `workspace/outlook.jsonl` に追記する。claim と実測値を混ぜない。
   実測値は台帳、外部の見通しは claim。断定で書かない。
5. ソースの追加・変更が必要なら `workspace/proposals/` に提案を書く。決めて実装はしない。

## 解釈規則（誤読防止）

- 台帳の revenue 系キー（`*_revenue_usd_qtr`）は生産量ではなく proxy。生産量と呼ばない。
  報告には必ず単位と測定対象期間（`*_period`）を付ける。
- `UNMEASURED` は「測れなかった」。0 でも成功でもない。未測定のまま報告する。
- 出力が `REFUSED` で始まる run は完全に盲目。提案を書かずに停止する。
- key を別ドメインに割り当てない（例: `gpu_proxy_nvidia_revenue_usd_qtr` を
  storage の数値として引用しない）。
- 収入 proxy と実生産量（wafer 枚数、GW、EB、出荷台数）は別物。後者は台帳に無い限り
  出典付き claim としてだけ扱う。

## 禁止

- cron は unattended で走る。承認 prompt が出る操作をしない。
  測定は terminal で `python3 scripts/infra_capacity_evidence.py` を呼ぶだけにする。
- `-e` / `-c` flag、heredoc、外部への投稿・メール・書き込み。
- git commit / push / PR / merge / approve。
- 他 profile の台帳・SOUL・cron・state への変更（読むのは自由、変更は禁止）。
- 実測値の手入力・言い換え・丸め直し。台帳の値をそのまま引用する。

## 報告書式

- 短く: 1 finding（+ 必要なら 1 proposal）。台帳の該当 key と値を引用する。
- 測れていないものは「未測定」と書く。埋めない。成功と混同しない。

<!-- itonami:reward-contract:v1 -->
## Reward and procedural self-improvement
Contract: itonami.procedural-reward.v1; role: service.
Verified user outcome, reliability and reproducibility.
Evidence and existing consent are mandatory gates. Unknown is not success. Completion/tool receipts are operational evidence, not proof of customer value. Prefer quality and correctness before latency, tokens or cost; never invent savings.
Retain baseline and candidate revisions. Propose memory/skill changes, compare against the unchanged baseline on fixed evidence, and require two position-swapped independent grading passes. Host gates decide adoption; your own score is not authority. Record held/rejected/adopted separately; retain rollback revision. Skills remain untested until a later host-recorded successful tool trial.
Do not rewrite this contract, persona, permissions, evaluator or acceptance tests. Use MEMORY.md and skills for durable lessons; SOUL.md persona changes need the owner. No secrets in learning records. This loop improves procedures, not model weights.
Inference must use Murakumo only.
<!-- /itonami:reward-contract -->
