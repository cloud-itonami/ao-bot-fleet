#!/bin/bash
# Hermes only runs .py/.sh as a cron `script`; the logic lives in fleet-kaizen-audit.cljk (kotoba).
set -eu
cd "$(dirname "$0")"
exec /opt/homebrew/bin/kbb --backend sci fleet-kaizen-audit.cljk "$@"
