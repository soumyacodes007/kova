"""`cadrecover task sample`: what a new miner developer gets (owner: agent C).

A fresh challenge is created exactly as a validator would, but only two files leave the
private store: the PUBLIC record (names, ranges, edit rules, no values) and the drawing PNG.
The private record, the reference STEP files and draftwright's SVG are never copied.
The challenge is then retired, so it can never be a live round: its drawing is public now.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from cadrecover.protocol import PublicChallenge

PUBLIC_FILES = ("challenge.json", "drawing.png")


def write_sample(family: str, out: Path, *, new_challenge=None, retire=None) -> dict:
    """Create one challenge and copy its public files to `out/<challenge_id>/`."""
    if new_challenge is None:
        from cadrecover.challenges.pipeline import new_challenge
    info = new_challenge(family=family)
    public_src = Path(info["public_record"])
    png_src = Path(info["drawing_png"])
    PublicChallenge.model_validate_json(public_src.read_text())  # must parse as the public record

    dest = Path(out) / info["challenge_id"]
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(public_src, dest / "challenge.json")
    shutil.copyfile(png_src, dest / "drawing.png")

    if retire is None:
        def retire(cid: str) -> None:
            from cadrecover.storage import db

            db.retire_challenge(db.connect(), cid, "practice sample handed out; drawing is public")
    retire(info["challenge_id"])
    return {"challenge_id": info["challenge_id"], "family": family, "dir": str(dest),
            "public_record": str(dest / "challenge.json"), "drawing_png": str(dest / "drawing.png")}
