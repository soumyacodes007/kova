#!/usr/bin/env bash
# `make demo`: from whatever state the machine is in, bring the whole subnet up and run it.
#
#   localnet up + producing blocks -> dev wallets -> subnet + neurons bootstrapped -> engine images
#   -> 5 miners (axons served, engines committed) -> doctor -> validator rounds -> audit -> weights
#
# Every step is idempotent. Local network only; nothing binds beyond 127.0.0.1.
#
#   bash scripts/demo.sh              # set up, then open the 3-pane tmux session `cadrecover-demo`
#   DEMO_HEADLESS=1 bash scripts/demo.sh   # same sequence on stdout, no tmux; exit 1 on any failure (the backend gate)
#   bash scripts/demo.sh down         # kill the tmux session and stop the miners (ALL=1 also stops the localnet)
#   bash scripts/demo.sh pipeline     # (internal) validator rounds -> audit -> weights -> gate check
#
# Knobs: ROUNDS=2  DEADLINE=180 (s per round)  AUDIT_TOP=1  DEMO_REUSE_MINERS=1 (keep running miners)
#        DEMO_SKIP_SETUP=1 (assume localnet, wallets, bootstrap and miners are up)  SESSION=cadrecover-demo
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
HOME_DIR="${CADRECOVER_HOME:-$HOME/.cadrecover}"
CR="$HOME_DIR/envs/services/bin/cadrecover"
PY="$HOME_DIR/envs/services/bin/python"
LOGS="$HOME_DIR/runtime/logs"
SESSION="${SESSION:-cadrecover-demo}"
ROUNDS="${ROUNDS:-2}"
DEADLINE="${DEADLINE:-180}"
AUDIT_TOP="${AUDIT_TOP:-1}"
STRATEGIES=(mock-oracle mock-noisy diag-constant diag-wrong-holes diag-crash)
WALLET_NAMES=(owner validator miner1 miner2 miner3 miner4 miner5)
MINER_PORTS=(8101 8102 8103 8104 8105)
export CADRECOVER_DEV_ORACLE=1   # the mock miners and the auditor's mock engines read the local private record
mkdir -p "$LOGS"

say() { printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mdemo failed: %s\033[0m\n' "$*" >&2; exit 1; }

[ -x "$CR" ] || die "$CR not found: run 'make envs'"

# ------------------------------------------------------------------ down

if [ "${1:-}" = "down" ]; then
  tmux kill-session -t "$SESSION" 2>/dev/null && echo "tmux session $SESSION closed" || echo "no tmux session $SESSION"
  bash scripts/run-miners.sh stop
  if [ "${ALL:-}" = "1" ]; then docker compose down; else echo "localnet left running (ALL=1 make demo-down stops it)"; fi
  exit 0
fi

# ------------------------------------------------------------------ steps

wait_for_chain() {
  for _ in $(seq 1 60); do
    "$CR" chain heartbeat --network local --wait 1 >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

miners_healthy() {
  for p in "${MINER_PORTS[@]}"; do curl -sf --max-time 2 "http://127.0.0.1:$p/v1/health" >/dev/null || return 1; done
}

setup() {
  say "1/6 localnet"
  docker compose up -d localnet
  wait_for_chain || die "the localnet is not producing blocks (docker compose logs localnet)"
  "$CR" chain heartbeat --network local | "$PY" -c "import json,sys; d=json.load(sys.stdin); print('producing blocks:', d['first'], '->', d['second'])"

  say "2/6 dev wallets"
  missing=0
  for n in "${WALLET_NAMES[@]}"; do [ -f "$HOME_DIR/wallets/$n/coldkey" ] || missing=1; done
  if [ "$missing" = 1 ]; then "$CR" setup wallets >/dev/null && echo "created dev wallets in $HOME_DIR/wallets"; else echo "present"; fi

  say "3/6 subnet bootstrap (idempotent)"
  "$CR" chain bootstrap >"$LOGS/bootstrap.log" 2>&1 || { tail -n 20 "$LOGS/bootstrap.log" >&2; die "chain bootstrap failed"; }
  "$PY" -c "
import json; s = json.load(open('$HOME_DIR/chain.json'))
print('netuid', s['netuid'], '| validator uid', s['neurons']['validator']['uid'], '| commit-reveal', 'on' if s.get('commit_reveal_enabled') else 'off')"

  say "4/6 engine images"
  bash scripts/build-engines.sh "${STRATEGIES[@]}" || die "engine image build failed"

  say "5/6 miners (5 local, axons served, engines committed)"
  if [ "${DEMO_REUSE_MINERS:-}" = "1" ] && miners_healthy; then
    echo "reusing the running miners"
  else
    bash scripts/run-miners.sh || die "miners did not start"
  fi

  say "6/6 doctor"
  "$CR" doctor || die "doctor reported failures"
}

# Gate check: the round finished, weights are on chain, and a fresh audit passed.
verify() {
  say "backend gate check"
  local status_json
  status_json="$("$CR" status --json --no-chain)"
  STATUS_JSON="$status_json" "$PY" - "$1" "$HOME_DIR/chain.json" <<'PY'
import json, os, sys

start, chain_json = sys.argv[1], sys.argv[2]
d = json.loads(os.environ["STATUS_JSON"])
state = json.load(open(chain_json))
problems, states = [], []
run, batch = d["run"], d["batch"]
if not run or run["status"] != "done":
    problems.append("latest round is not done")
if not batch:
    problems.append("no weight batch")
else:
    states = [r["state"] for r in batch["receipts"]]
    want = "committed" if state.get("commit_reveal_enabled") else "revealed"
    if want not in states and "revealed" not in states:
        problems.append(f"weights never reached {want} (receipts: {states})")
fresh = [a for a in d["audits"] if a["at"] >= start]
if not fresh:
    problems.append("no audit ran in this demo")
for a in fresh:
    if a["verdict"] != "pass":
        problems.append(f"audit uid {a['uid']} engine {a['engine'][:19]}: {a['verdict']} ({a['reason']})")
for p in problems:
    print("  x", p)
if not problems:
    print("  ok round", run["run_id"], "done | weights", states[-1], "| audits",
          ", ".join(f"uid {a['uid']} {a['verdict']}" for a in fresh))
sys.exit(1 if problems else 0)
PY
}

# A miner whose latest audit failed earns nothing until a clean audit (aggregate.failed_audits). Miners were just
# re-committed to their real engines, so re-audit those hotkeys first; otherwise an old failure would block the round.
clear_failed_audits() {
  local hotkeys
  hotkeys="$("$CR" status --json --no-chain | "$PY" -c "
import json, sys
seen, bad = set(), []
for a in json.load(sys.stdin)['audits']:  # newest first
    if a['hotkey'] not in seen:
        seen.add(a['hotkey'])
        if a['verdict'] != 'pass': bad.append(a['hotkey'])
print(' '.join(bad))")"
  [ -z "$hotkeys" ] && return 0
  say "re-audit miners whose latest audit did not pass"
  local args=()
  for h in $hotkeys; do args+=(--hotkey "$h"); done
  "$CR" auditor run "${args[@]}"
}

pipeline() {
  local start
  start="$(date -u +%Y-%m-%dT%H:%M:%S)"
  clear_failed_audits
  say "validator: $ROUNDS round(s), deadline ${DEADLINE}s"
  "$CR" validator run --rounds "$ROUNDS" --deadline "$DEADLINE"
  say "auditor: re-run the committed engine of the top $AUDIT_TOP miner(s) on hidden tasks"
  "$CR" auditor run --top "$AUDIT_TOP"
  say "weights on chain"
  "$CR" chain weights
  if [ "${1:-}" = "--status" ]; then say "status"; "$CR" status; fi
  verify "$start"
}

# ------------------------------------------------------------------ run

case "${1:-}" in
  pipeline) pipeline "${2:-}"; exit $? ;;
  "") ;;
  *) die "unknown argument '$1' (use: down | pipeline)" ;;
esac

[ "${DEMO_SKIP_SETUP:-}" = "1" ] || setup

if [ "${DEMO_HEADLESS:-}" = "1" ]; then
  pipeline --status
  say "demo ok"
  exit 0
fi

command -v tmux >/dev/null || die "tmux not installed (apt install tmux), or run DEMO_HEADLESS=1 make demo"
tmux kill-session -t "$SESSION" 2>/dev/null || true
ENVP="CADRECOVER_DEV_ORACLE=1 CADRECOVER_HOME=$HOME_DIR"
# pane 1: the validator, then the audit and the weights; pane 2: what the miners and the validator are doing; pane 3: status
tmux new-session -d -s "$SESSION" -x 200 -y 56 -c "$REPO" \
  "env $ENVP bash scripts/demo.sh pipeline; rc=\$?; echo; echo \"[demo] finished, exit \$rc. Ctrl-b d detaches; make demo-down closes it.\"; exec bash"
tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-border-format ' #{pane_title} '
tmux select-pane -t "$SESSION:0.0" -T 'validator · audit · weights'
tmux split-window -t "$SESSION:0.0" -v -l 45% -c "$REPO" \
  "env $ENVP bash -c 'tail -q -n 0 -F $LOGS/miner-*.log 2>/dev/null | sed -u \"s/^/[miner log] /\" & exec $CR events --follow --last 6'"
tmux select-pane -t "$SESSION:0.1" -T 'miners · jobs · events'
tmux split-window -t "$SESSION:0.1" -v -l 55% -c "$REPO" "env $ENVP $CR status --watch"
tmux select-pane -t "$SESSION:0.2" -T 'status'
tmux select-pane -t "$SESSION:0.0"

if [ -t 1 ] && [ -z "${TMUX:-}" ]; then
  exec tmux attach -t "$SESSION"
elif [ -n "${TMUX:-}" ]; then
  tmux switch-client -t "$SESSION"
else
  echo "demo is running in tmux session '$SESSION': tmux attach -t $SESSION"
fi
