"""Runs one miner submission at one parameter set, inside the sandbox container.

Standalone on purpose: only build123d is importable here, not cadrecover.

  /job/source.py       miner code (read-only mount)
  /job/overrides.json  what build_part receives: {} at s0, changed keys at edits
  /out/candidate.step  the resulting solid
  /out/result.json     {"ok", "error_type", "error", "seconds"}

The import allowlist is a validity rule (a submission must be plain build123d
code); the container (no network, read-only, capped) is the security boundary.
"""

import ast
import json
import os
import signal
import sys
import time
import traceback

ALLOWED_IMPORTS = {"build123d", "math", "typing", "dataclasses"}
FORBIDDEN_CALLS = {"__import__", "eval", "exec", "compile", "open", "input", "breakpoint", "globals", "vars"}
TIME_LIMIT = int(os.environ.get("TIME_LIMIT", "60"))
OUT = "/out"


def write(result):
    with open(os.path.join(OUT, "result.json"), "w") as f:
        json.dump(result, f)


def check_source(src: str):
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return f"forbidden import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.level or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return f"forbidden import: {node.module}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            return f"forbidden call: {node.func.id}"
        elif isinstance(node, ast.Attribute) and node.attr.startswith("__") and node.attr.endswith("__"):
            return f"forbidden dunder attribute: {node.attr}"
    if not any(isinstance(n, ast.FunctionDef) and n.name == "build_part" for n in tree.body):
        return "no top-level build_part function"
    return None


def timeout(signum, frame):
    raise TimeoutError(f"build_part exceeded {TIME_LIMIT}s")


def main():
    t0 = time.monotonic()
    try:
        src = open("/job/source.py").read()
        overrides = json.load(open("/job/overrides.json"))
        problem = check_source(src)
        if problem:
            write({"ok": False, "error_type": "invalid_source", "error": problem, "seconds": 0.0})
            return 0
        import build123d

        signal.signal(signal.SIGALRM, timeout)
        signal.alarm(TIME_LIMIT)
        namespace = {"__name__": "miner_solution"}
        exec(compile(src, "miner_solution.py", "exec"), namespace)  # noqa: S102 - this is the sandbox
        part = namespace["build_part"](dict(overrides))
        signal.alarm(0)
        if not isinstance(part, build123d.Shape):
            write({"ok": False, "error_type": "wrong_return_type",
                   "error": f"build_part returned {type(part).__name__}, not a build123d shape",
                   "seconds": time.monotonic() - t0})
            return 0
        build123d.export_step(part, os.path.join(OUT, "candidate.step"))
        write({"ok": True, "error_type": None, "error": None, "seconds": time.monotonic() - t0})
    except TimeoutError as e:
        write({"ok": False, "error_type": "timeout", "error": str(e), "seconds": time.monotonic() - t0})
    except BaseException as e:  # noqa: BLE001 - any miner failure is a result, not a crash
        tb = traceback.format_exception_only(type(e), e)[-1].strip()
        write({"ok": False, "error_type": "exception", "error": tb[:500], "seconds": time.monotonic() - t0})
    return 0


if __name__ == "__main__":
    sys.exit(main())
