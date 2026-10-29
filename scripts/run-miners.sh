#!/usr/bin/env bash
# Start 5 local miners (one wallet + port + strategy each) and write ~/.cadrecover/miners.json
# (static discovery + strategy labels). If the chain is bootstrapped (~/.cadrecover/chain.json),
# each miner also publishes its endpoint with ServeAxon so the validator finds it in the metagraph.
# Miners bind 127.0.0.1 only; the chain rejects loopback, so they advertise this host's LAN IP and
# a same-machine validator maps it back to loopback (chain/neurons.py).
#
# Strategies are MOCKS until a vision-model key is configured (see miner/strategies.py).
#   bash scripts/run-miners.sh          # start
#   bash scripts/run-miners.sh stop     # stop
set -euo pipefail
HOME_DIR="${CADRECOVER_HOME:-$HOME/.cadrecover}"
CR="$HOME_DIR/envs/services/bin/cadrecover"
PY="$HOME_DIR/envs/services/bin/python"
LOGS="$HOME_DIR/runtime/logs"
mkdir -p "$LOGS"

# uid  wallet  port  strategy
MINERS=(
  "1 miner1 8101 mock-oracle"
  "2 miner2 8102 mock-noisy"
  "3 miner3 8103 diag-constant"
  "4 miner4 8104 diag-wrong-holes"
  "5 miner5 8105 diag-crash"
)

pkill -f '[c]adrecover miner run' || true
[ "${1:-}" = "stop" ] && { echo "miners stopped"; exit 0; }

VALIDATOR=$("$PY" -c "import bittensor as bt; print(bt.Wallet('validator','default',path='$HOME_DIR/wallets').hotkey.ss58_address)")
entries=()
for m in "${MINERS[@]}"; do
  read -r uid wallet port strategy <<<"$m"
  CADRECOVER_DEV_ORACLE=1 nohup "$CR" miner run --wallet "$wallet" --strategy "$strategy" --port "$port" \
    --validator "$VALIDATOR" > "$LOGS/miner-$uid.log" 2>&1 &
  hk=$("$PY" -c "import bittensor as bt; print(bt.Wallet('$wallet','default',path='$HOME_DIR/wallets').hotkey.ss58_address)")
  entries+=("{\"hotkey\": \"$hk\", \"uid\": $uid, \"registered_at_block\": 0, \"url\": \"http://127.0.0.1:$port\", \"label\": \"$strategy\"}")
done
( IFS=,; echo "[${entries[*]}]" ) | "$PY" -m json.tool > "$HOME_DIR/miners.json"

for m in "${MINERS[@]}"; do
  read -r uid wallet port strategy <<<"$m"
  for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$port/v1/health" >/dev/null && break; sleep 0.25; done
  echo "uid $uid  $strategy  $(curl -s "http://127.0.0.1:$port/v1/health")"
done

if [ -f "$HOME_DIR/chain.json" ]; then
  for m in "${MINERS[@]}"; do
    read -r uid wallet port strategy <<<"$m"
    "$CR" chain serve-axon --wallet "$wallet" --port "$port" 2>/dev/null | "$PY" -c "import json,sys; d=json.load(sys.stdin); print('axon', d['wallet'], 'uid', d['uid'], d['axon'])"
    # engine commitment: the image the auditor will re-run (scripts/build-engines.sh builds them)
    if digest=$(docker image inspect --format '{{.Id}}' "cadrecover-engine:$strategy" 2>/dev/null); then
      "$CR" chain commit-engine --wallet "$wallet" --digest "$digest" --strategy "$strategy@0.1.0" 2>/dev/null         | "$PY" -c "import json,sys; d=json.load(sys.stdin); print('engine', d['wallet'], d['e'][:19], 'block', d['block'])"
    fi
  done
fi
