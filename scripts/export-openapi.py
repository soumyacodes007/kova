#!/usr/bin/env python
"""Write docs/api/openapi.json and apps/web/lib/api-types.ts from the API's own schema (owner: agent C).

    ~/.cadrecover/envs/services/bin/python scripts/export-openapi.py            # regenerate both files
    ~/.cadrecover/envs/services/bin/python scripts/export-openapi.py --check    # fail if either is stale

TypeScript comes from `openapi-typescript` (pinned below, run through npx) when npx is on PATH, otherwise from
the pure-Python fallback `scripts/gen-ts-types.py`; force one with --types npx|python. The app is built over a
throwaway database and never touches the chain, so this is safe to run anywhere.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

OPENAPI_JSON = REPO / "docs" / "api" / "openapi.json"
TS_TYPES = REPO / "apps" / "web" / "lib" / "api-types.ts"
OPENAPI_TYPESCRIPT = "openapi-typescript@7.9.1"  # pinned


def build_spec() -> dict:
    from cadrecover.api.app import create_app

    with tempfile.TemporaryDirectory() as tmp:
        app = create_app(Path(tmp) / "openapi.sqlite", public_dir=Path(tmp), runs_dir=Path(tmp), chain_rpc=None,
                         state_file=Path(tmp) / "none.json")
        return app.openapi()


def render_json(spec: dict) -> str:
    return json.dumps(spec, indent=2, ensure_ascii=False) + "\n"


def types_via_python(spec_path: Path, out: Path) -> None:
    gen = importlib.util.spec_from_file_location("gen_ts_types", REPO / "scripts" / "gen-ts-types.py")
    mod = importlib.util.module_from_spec(gen)
    gen.loader.exec_module(mod)
    mod.main([str(spec_path), "-o", str(out)])


def types_via_npx(spec_path: Path, out: Path) -> None:
    npx = shutil.which("npx")
    # relative paths: under WSL npx is the Windows one and cannot resolve /mnt/c/... absolute paths
    cmd = [npx, "--yes", OPENAPI_TYPESCRIPT, str(spec_path.relative_to(REPO)), "-o", str(out.relative_to(REPO))]
    r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not out.exists():
        raise RuntimeError(f"{OPENAPI_TYPESCRIPT} failed:\n{r.stdout}\n{r.stderr}")
    out.write_text(out.read_text(encoding="utf-8").replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def make_types(spec_path: Path, out: Path, mode: str) -> str:
    out.parent.mkdir(parents=True, exist_ok=True)
    if mode in ("auto", "npx") and shutil.which("npx"):
        try:
            types_via_npx(spec_path, out)
            return "npx " + OPENAPI_TYPESCRIPT
        except (RuntimeError, subprocess.TimeoutExpired, OSError) as e:
            if mode == "npx":
                raise
            print(f"npx generation failed, falling back to python: {str(e)[:200]}", file=sys.stderr)
    elif mode == "npx":
        raise SystemExit("npx not found on PATH")
    types_via_python(spec_path, out)
    return "scripts/gen-ts-types.py"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--types", choices=["auto", "npx", "python"], default="auto")
    p.add_argument("--check", action="store_true", help="exit 1 if the committed files differ from the API's schema")
    a = p.parse_args(argv)

    text = render_json(build_spec())
    if a.check:
        stale = not OPENAPI_JSON.exists() or OPENAPI_JSON.read_text(encoding="utf-8") != text
        print(f"{OPENAPI_JSON.relative_to(REPO)}: {'STALE' if stale else 'up to date'}")
        if not TS_TYPES.exists():
            print(f"{TS_TYPES.relative_to(REPO)}: MISSING")
            stale = True
        return 1 if stale else 0

    OPENAPI_JSON.parent.mkdir(parents=True, exist_ok=True)
    OPENAPI_JSON.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OPENAPI_JSON.relative_to(REPO)}")
    how = make_types(OPENAPI_JSON, TS_TYPES, a.types)
    print(f"wrote {TS_TYPES.relative_to(REPO)} via {how}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
