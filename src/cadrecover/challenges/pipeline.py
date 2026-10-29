"""Create a challenge end to end (services env; drives the CAD and drawing workers).

    seed -> parameters -> reference solid (CAD worker, self-tested) -> drawing (drawing worker,
    coverage-checked, scan look) -> private record (runtime/private) + public record (artifacts/public)
    -> SQLite.

A drawing that misses a required dimension is rejected and the part is
resampled with the next seed (logged as an event). Only the PNG is published:
draftwright's SVG stays private, since its geometry is machine-readable.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
import subprocess
from pathlib import Path

from cadrecover import paths
from cadrecover.challenges.families import plate_spec
from cadrecover.protocol import (
    Artifact,
    FeatureMeasurement,
    ParameterSet,
    PrivateChallenge,
    PublicChallenge,
)
from cadrecover.storage import db

SPECS = {"plate": plate_spec}
TITLES = {"plate": "Mounting plate"}


class ChallengeError(RuntimeError):
    pass


def _run(env: str, module: str, *args: str) -> dict:
    proc = subprocess.run([str(paths.env_python(env)), "-m", module, *args], capture_output=True, text=True,
                          cwd=paths.HOME, timeout=600)
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.startswith("{")]
    if not lines:
        raise ChallengeError(f"{module} failed ({proc.returncode}):\n{proc.stderr[-2000:]}")
    out = json.loads(lines[-1])
    if proc.returncode != 0:
        raise ChallengeError(f"{module}: {out.get('error', out)}")
    return out


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def new_challenge(family: str = "plate", seed: int | None = None, *, scan_look: bool = True,
                  max_attempts: int = 5) -> dict:
    if family not in SPECS:
        raise ChallengeError(f"unknown family {family!r}")
    spec = SPECS[family]
    paths.ensure()
    con = db.connect()
    seed = secrets.randbits(62) if seed is None else seed
    challenge_id = "ch_" + secrets.token_hex(8)  # opaque: says nothing about seed or parameters
    private_dir = paths.PRIVATE / challenge_id
    private_dir.mkdir(mode=0o700, parents=True)

    attempts = []
    for attempt in range(max_attempts):
        s = seed + attempt
        params = _run("cad", "cadrecover.challenges.cad_worker", "sample", "--family", family, "--seed", str(s))["params"]
        ref = _run("cad", "cadrecover.challenges.cad_worker", "build", "--family", family,
                   "--params", json.dumps(params), "--out", str(private_dir), "--name", "s0")
        number = f"LEGACY-1987-{s % 10000:04d}"
        drawing = _run("drawing", "cadrecover.challenges.drawing_worker", "draw", "--step", ref["step"],
                       "--out", str(private_dir), "--title", TITLES[family], "--number", number,
                       "--require", json.dumps(spec.required_labels(params)), "--seed", str(s),
                       *([] if scan_look else ["--clean"]))
        attempts.append({"seed_offset": attempt, "coverage_ok": drawing["coverage"]["ok"],
                         "missing": drawing["coverage"]["missing_required"], "unplaced": drawing["coverage"]["unplaced"]})
        if drawing["coverage"]["ok"]:
            break
        db.add_event(con, "challenge.drawing_rejected", {"challenge_id": challenge_id, "attempt": attempt,
                                                         "missing": drawing["coverage"]["missing_required"],
                                                         "unplaced": drawing["coverage"]["unplaced"]})
    else:
        shutil.rmtree(private_dir)
        raise ChallengeError(f"no drawing passed coverage in {max_attempts} attempts: {attempts}")

    edits = _run("cad", "cadrecover.challenges.cad_worker", "edits", "--family", family,
                 "--params", json.dumps(params), "--seed", str(seed + attempt), "--out", str(private_dir))["sets"]

    public_dir = paths.PUBLIC / challenge_id
    public_dir.mkdir(parents=True)
    png = public_dir / "drawing.png"
    shutil.copyfile(drawing["png"], png)
    Path(drawing["png"]).unlink()  # the only copy of the published image lives in the public store

    public = PublicChallenge(
        challenge_id=challenge_id,
        family=family,
        frame=spec.FRAME,
        parameters=spec.parameter_specs(params),
        edit_rules=spec.EDIT_RULES,
        critical_features=spec.critical_feature_specs(params),
        drawing=Artifact(path=f"{challenge_id}/drawing.png", sha256=_sha256(png), media_type="image/png"),
    )
    svg = Path(drawing["svg"])
    private = PrivateChallenge(
        challenge_id=challenge_id,
        family=family,
        seed=seed + attempt,
        sets=[ParameterSet(
            index=0,
            values=params,
            overrides={},
            reference=Artifact(path=f"{challenge_id}/s0.step", sha256=ref["sha256"], media_type="model/step"),
            measurements=[FeatureMeasurement(**m) for m in ref["measurements"]],
            volume_mm3=ref["volume"],
        )] + [ParameterSet(
            index=e["index"],
            values=e["values"],
            overrides=e["overrides"],
            reference=Artifact(path=f"{challenge_id}/s{e['index']}.step", sha256=e["sha256"], media_type="model/step"),
            measurements=[FeatureMeasurement(**m) for m in e["measurements"]],
            volume_mm3=e["volume"],
            max_feature_shift_mm=e["max_feature_shift_mm"],
            reference_self_iou=e["reference_self_iou"],
        ) for e in edits],
        drawing_svg=Artifact(path=f"{challenge_id}/{svg.name}", sha256=_sha256(svg), media_type="image/svg+xml"),
        drawing_lint={"lint": drawing["lint"], "coverage": drawing["coverage"], "attempts": attempts},
    )
    private_path = private_dir / "private.json"
    private_path.write_text(private.model_dump_json(indent=1))
    private_path.chmod(0o600)
    (public_dir / "challenge.json").write_text(public.model_dump_json(indent=1))
    db.save_challenge(con, public, private_path)

    # Operator output: public facts only. Ground truth stays in the private folder.
    return {
        "challenge_id": challenge_id,
        "family": family,
        "drawing_png": str(png),
        "public_record": str(public_dir / "challenge.json"),
        "private_record": str(private_path),
        "attempts": len(attempts),
        "lint": drawing["lint"],
        "coverage": {k: drawing["coverage"][k] for k in ("ok", "ledger_requirements", "missing_required", "unplaced")},
    }
