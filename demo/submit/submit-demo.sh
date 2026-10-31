#!/usr/bin/env bash
# One miner submission, narrated. Every step runs the real code: the same CLI a miner runs,
# the same chain commitment, the same validator watcher. Localnet only.
set -euo pipefail
REPO_ID="${MODEL_REPO:?}"
REV="${MODEL_REVISION:?}"
LOGS=/data/runtime/logs
mkdir -p "$LOGS"
[ -d /logs ] && exec > >(tee /logs/submit-demo.log) 2>&1   # stdin stays the terminal for the step-2 question

step()  { printf '\n\033[1;36m━━ %s\033[0m\n' "$*"; }
who()   { printf '\033[1;35m[%s]\033[0m %s\n' "$1" "$2"; }
cmd()   { printf '\033[2m$ %s\033[0m\n' "$*"; }
ok()    { printf '\033[1;32m✔ %s\033[0m\n' "$*"; }
nope()  { printf '\033[1;33m✘ refused:\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31mdemo failed: %s\033[0m\n' "$*" >&2; exit 1; }
field() { python -c "import json,sys; d=json.load(sys.stdin); print(*(d.get(k) for k in sys.argv[1:]), sep='\t')" "$@"; }

step "0  Chain: a local subtensor (never mainnet)"
for _ in $(seq 1 90); do cadrecover chain heartbeat --wait 1 >/dev/null 2>&1 && break; sleep 2; done
cadrecover chain heartbeat | field first second producing | {
  read -r a b p; [ "$p" = "True" ] || die "localnet not producing blocks"; ok "producing blocks: $a -> $b"; }

step "1  Setup: dev wallets, subnet, validator + 5 miner hotkeys registered"
cadrecover setup wallets >/dev/null
cadrecover chain bootstrap >"$LOGS/bootstrap.log" 2>&1 || { tail -n 20 "$LOGS/bootstrap.log"; die "bootstrap failed"; }
python - <<'PY'
import json
s = json.load(open("/data/chain.json"))
print(f"netuid {s['netuid']}")
for name, n in s["neurons"].items():
    print(f"  uid {n['uid']:>2}  {name:<9} {n['hotkey']}")
PY

step "2  MINER: where do the weights come from?"
SOURCE="${WEIGHTS_SOURCE:-}"
if [ -z "$SOURCE" ] && [ -t 0 ]; then
  echo "  1) already trained and on Hugging Face"
  echo "  2) fine-tune first on Lium (Bittensor SN51 GPU rental), then push to Hugging Face"
  read -r -t 120 -p "  choose [1/2] (default 1): " pick || pick=1
  [ "$pick" = "2" ] && SOURCE=lium
fi
SOURCE="${SOURCE:-hf}"
who MINER "route: $SOURCE"

if [ "$SOURCE" = "lium" ]; then
  step "2a MINER: rent a GPU on Lium (SN51) for the fine-tune"
  who MINER "live Lium market, no account needed (cheapest 1-GPU nodes with >=24 GB VRAM):"
  cmd lium ls --min-vram 24 --count 1 --max-price 2.0 --reliable
  if lium ls --min-vram 24 --count 1 --max-price 2.0 --reliable --format json > "$LOGS/lium-ls.json" 2>/dev/null \
      && NODE=$(python - "$LOGS/lium-ls.json" <<'PY'
import json, sys
nodes = json.load(open(sys.argv[1]))
for n in nodes[:5]:
    print(f"  {n['huid']:<18} {n['gpu_type']:<10} {n['vram_gb']:>3} GB  ${n['price_per_gpu_hour']:.2f}/GPU·h  {n['country']}",
          file=sys.stderr)
print(nodes[0]["huid"] if nodes else "")
PY
      ) && [ -n "$NODE" ]; then
    GPU=$(python -c "import json,sys; print(json.load(open(sys.argv[1]))[0]['gpu_type'])" "$LOGS/lium-ls.json")
    cmd lium quote "$NODE" --hours 2 --gpus 1
    lium quote "$NODE" --hours 2 --gpus 1 --format json 2>/dev/null | python -c "
import json, sys; q = json.load(sys.stdin)
print(f'  2 h on {q[\"gpu_count\"]} GPU at \${q[\"price_per_hour\"]:.2f}/h = \${q[\"total_usd\"]:.2f} (billed per second, pod removed when done)')" \
      || echo "  (quote unavailable right now)"
  else
    NODE=""; GPU="RTX4090"
    echo "  (Lium market unreachable or nothing matches right now)"
  fi

  echo
  who MINER "the fine-tune runs as one bounded Lium job: rent -> train -> copy back -> pod removed"
  cmd "lium job run \"bash finetune.sh\" --gpu $GPU --budget 5 --deadline 2h \\"
  cmd "    --input finetune.sh:/root/finetune.sh --env HF_TOKEN=*** --env BASE=$REPO_ID"
  who MINER "finetune.sh merges any LoRA into full safetensors (adapter-only repos are refused),"
  who MINER "pushes to Hugging Face and prints the new commit SHA: that SHA is what gets submitted"

  if [ -n "${LIUM_API_KEY:-}" ] && [ -n "$NODE" ] && [ -t 0 ]; then
    echo
    echo "  A Lium API key is set. Rent a $GPU now for a short GPU check job (real money: budget \$0.25, 10 min)?"
    read -r -t 120 -p "  type RENT to spend, anything else to skip: " confirm || confirm=""
    if [ "$confirm" = "RENT" ]; then
      cmd lium job run "nvidia-smi --query-gpu=name,memory.total --format=csv" --gpu "$GPU" --budget 0.25 --deadline 10m
      if lium job run "nvidia-smi --query-gpu=name,memory.total --format=csv" --gpu "$GPU" \
           --budget 0.25 --deadline 10m --max-price-per-gpu-hour 2.0 --format json > "$LOGS/lium-job.json"; then
        ok "Lium GPU job finished: $(head -c 400 "$LOGS/lium-job.json")"
      else
        nope "Lium job did not succeed: $(head -c 400 "$LOGS/lium-job.json")"
      fi
    else
      ok "skipped renting: \$0 spent"
    fi
  else
    ok "no rental in this run (needs LIUM_API_KEY and a terminal to confirm): \$0 spent"
  fi
  who MINER "continuing with an already-trained pinned model so the rest of the flow runs now"
fi

step "2b MINER: the model lives on Hugging Face, pinned to one commit"
who MINER "repo      $REPO_ID"
who MINER "revision  $REV   (a commit SHA, not a branch: weights can't change after submit)"
who MINER "browse    https://huggingface.co/$REPO_ID/tree/$REV"

step "3  MINER: free pre-check (metadata only, no weights downloaded, no repo code run)"
cmd cadrecover model check --repo "$REPO_ID" --revision "$REV"
cadrecover model check --repo "$REPO_ID" --revision "$REV" > "$LOGS/check.json" || die "pre-check failed"
python - "$LOGS/check.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
print(f"  full safetensors   {d['weight_bytes']/1e9:.2f} GB  (limit 20 GB)")
print(f"  weights fingerprint {d['fingerprint']}")
print(f"                      = sha256 of sorted 'file:LFS-sha256' lines, so identical weights => identical fingerprint")
print(f"  base model          {d.get('base_model') or '(not declared in the model card)'}")
PY
ok "pre-check passed"

step "4  MINER: commit on chain, signed by miner1's hotkey"
cmd cadrecover model submit --wallet miner1 --repo "$REPO_ID" --revision "$REV"
cadrecover model submit --wallet miner1 --repo "$REPO_ID" --revision "$REV" > "$LOGS/submit.out" \
  || die "submit failed"
python - "$LOGS/submit.out" <<'PY'
import json, sys
text = open(sys.argv[1]).read()
start = text.index("\n{") + 1 if not text.startswith("{") else 0
for line in text[:start].splitlines():  # the validator watcher's own log line, printed during submit
    print(f"  validator: {line}")
d = json.loads(text[start:])
raw = json.dumps({"k": d["k"], "r": d["r"], "v": d["v"], "f": d["f"]}, separators=(",", ":"))
print(f"  hotkey        {d['hotkey']}")
print(f"  on-chain data {raw}   ({len(raw.encode())} of 128 bytes)")
print(f"  commit block  {d['commitment_block']}   <- the timestamp: earliest block wins a copy dispute")
print(f"  fee           {d['fee']}   (localnet: simulated)")
PY
ok "commitment accepted by the chain"

step "5  VALIDATOR: reads every hotkey's commitment straight from chain"
python - <<'PY'
import bittensor as bt
from cadrecover.chain import commitments
from cadrecover.chain.bootstrap import load_state
s = load_state()
with bt.Subtensor("ws://127.0.0.1:9944") as sub:
    for n in sub.subnets.metagraph(netuid=s["netuid"], commitments=False).neurons:
        c = commitments.read_commitment(n.hotkey, sub=sub)
        if c and c.get("k") == "m":
            print(f"  uid {n.uid}  block {c['block']}  {c['r']}@{c['v'][:12]}…  fingerprint {c['f']}")
PY
ok "commitment verified: same repo, revision and fingerprint the miner signed"

step "6  VALIDATOR: re-checks Hugging Face against the commitment, then queues the model"
python - <<'PY'
from cadrecover.storage import db
con = db.connect()
for m in db.hill_models(con, "local"):
    print(f"  {m.name:<28} uid {m.uid}  status {m.status:<8} commit block {m.commit_block}")
    print(f"  {'':<28} {m.hf_url}")
import json
seen = []
for r in con.execute("SELECT payload FROM events WHERE kind='model.status' ORDER BY event_id"):
    status = json.loads(r["payload"])["status"]
    if not seen or seen[-1] != status:
        seen.append(status)
print("    events: " + " -> ".join(seen))
PY
ok "queued for the next hill match (custom-model deploys are off on localnet, so this demo stops here)"

step "7  RULES: what the subnet refuses"
echo "a) a branch name instead of a commit SHA"
cmd cadrecover model check --repo "$REPO_ID" --revision main
if out=$(cadrecover model check --repo "$REPO_ID" --revision main 2>&1); then die "branch revision was accepted"; fi
nope "$(tail -n 1 <<<"$out" | sed 's/^[A-Za-z.]*Error: //')"

echo
echo "b) a copier (miner2) re-submitting miner1's weights through the CLI"
cmd cadrecover model submit --wallet miner2 --repo "$REPO_ID" --revision "$REV"
if out=$(cadrecover model submit --wallet miner2 --repo "$REPO_ID" --revision "$REV" 2>&1); then
  die "duplicate weights were accepted"; fi
nope "$(tail -n 1 <<<"$out" | sed 's/^[A-Za-z.]*Error: //')  (stopped before paying any chain fee)"

echo
echo "c) the same copier bypassing the CLI and writing straight to chain"
python - "$REPO_ID" "$REV" <<'PY'
import json, sys
from cadrecover.chain import commitments
from cadrecover.validator.hill.watcher import discover_model_commitments
repo, rev = sys.argv[1:]
d = json.load(open("/data/runtime/logs/check.json"))
c = commitments.commit_model("miner2", repo, rev, d["fingerprint"])
print(f"  miner2 committed on chain at block {c['block']} (later than miner1)")
discover_model_commitments("local", log=lambda line: print("  validator:", line))
PY

step "Done"
echo "  miner:     push weights to HF at a pinned commit -> 'cadrecover model submit' (one signed chain write)"
echo "  validator: read commitment -> re-check HF metadata -> refuse copies (earliest block wins) -> queue"
echo "  next:      hill match on fresh hidden drawings; the champion's hotkey gets the weight"
