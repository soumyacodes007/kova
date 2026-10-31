#!/usr/bin/env bash
# Fresh localnet + the submit walkthrough, logs on screen and in runtime/submit-demo.log.
#   bash demo/submit/run.sh            # KEEP=1 leaves the chain running afterwards
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ../../runtime
dc() { docker compose -f compose.yaml "$@"; }

dc down -v --remove-orphans >/dev/null 2>&1 || true
dc build -q submit
dc up -d --quiet-pull chain >/dev/null 2>&1
status=0
# No pipe here: the container needs the real terminal to ask its question. It tees its own log.
dc run --rm submit || status=$?
[ "${KEEP:-}" = "1" ] || dc down -v >/dev/null 2>&1
echo "log saved: runtime/submit-demo.log"
exit "$status"
