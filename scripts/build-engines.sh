#!/usr/bin/env bash
# Build one engine image per local miner strategy; print strategy -> image ID (the committed digest).
set -euo pipefail
cd "$(dirname "$0")/.."
for s in "$@"; do
  docker build -q -f images/engine/Dockerfile --build-arg STRATEGY="$s" -t "cadrecover-engine:$s" src >/dev/null
  echo "$s $(docker image inspect --format '{{.Id}}' "cadrecover-engine:$s")"
done
