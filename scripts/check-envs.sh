#!/usr/bin/env bash
# Phase 1 check: every environment imports its libraries (and does real work with them).
set -euo pipefail
ENVS="${CADRECOVER_HOME:-$HOME/.cadrecover}/envs"

echo "== services"
"$ENVS/services/bin/python" - <<'PY'
import bittensor, fastapi, httpx, pydantic, rich, cadrecover.protocol as p
print(f"bittensor {bittensor.__version__} | fastapi {fastapi.__version__} | pydantic {pydantic.__version__} | protocol {p.PROTOCOL_VERSION}")
PY

echo "== cad"
"$ENVS/cad/bin/python" - <<'PY'
import sys, tempfile, os
import build123d as bd, cadrecover.protocol as p
part = bd.Box(10, 10, 2) - bd.Cylinder(2, 4)
path = os.path.join(tempfile.mkdtemp(), "t.step")
bd.export_step(part, path)
print(f"python {sys.version.split()[0]} | build123d {bd.__version__} | volume {part.volume:.3f} | step {os.path.getsize(path)} B | protocol {p.PROTOCOL_VERSION}")
PY

echo "== drawing"
"$ENVS/drawing/bin/python" - <<'PY'
import sys
from importlib.metadata import version
import build123d as bd, draftwright, pymupdf, cadrecover.protocol as p
from draftwright import build_drawing
print(f"python {sys.version.split()[0]} | build123d {bd.__version__} | draftwright {version('draftwright')} | pymupdf {version('pymupdf')} | protocol {p.PROTOCOL_VERSION}")
PY
