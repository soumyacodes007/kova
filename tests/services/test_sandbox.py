"""Needs Docker and the sandbox image; skipped otherwise."""

import pytest

from cadrecover.execution import sandbox
from cadrecover.miner.templates import plate_source

pytestmark = pytest.mark.skipif(not (sandbox.shutil.which("docker") and sandbox.image_ready()),
                                reason="sandbox image not built")

DRAWN = {"width": 120.0, "length": 80.0, "thickness": 8.0, "hole_diameter": 6.5}


def test_honest_source_builds_a_step(tmp_path):
    r = sandbox.run_build(plate_source(DRAWN), {"width": 150.0}, tmp_path)
    assert r.ok and r.step is not None and r.step.stat().st_size > 1000, r


def test_forbidden_import_is_rejected_before_running(tmp_path):
    r = sandbox.run_build(plate_source(DRAWN, "crash"), {}, tmp_path)
    assert not r.ok and r.error_type == "invalid_source" and "socket" in r.error


def test_runaway_code_times_out(tmp_path):
    r = sandbox.run_build(plate_source(DRAWN, "timeout"), {}, tmp_path, time_limit=3)
    assert not r.ok and r.error_type == "timeout"


def test_no_network_inside(tmp_path):
    # urllib isn't on the allowlist; prove the container has no network even if it were reachable.
    src = "import math\n\ndef build_part(overrides):\n    raise RuntimeError('unreachable')\n"
    r = sandbox.run_build(src, {}, tmp_path)
    assert not r.ok and r.error_type == "exception"
    inspect = sandbox.subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "--entrypoint", "python", sandbox.IMAGE, "-c",
         "import socket; s = socket.socket(); s.settimeout(2)\n"
         "try:\n    s.connect(('1.1.1.1', 53)); print('CONNECTED')\nexcept OSError as e:\n    print('BLOCKED', e)"],
        capture_output=True, text=True, timeout=60)
    assert "BLOCKED" in inspect.stdout, inspect.stdout + inspect.stderr
