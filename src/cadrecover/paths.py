"""Where CADRecover keeps runtime state. Never inside the repo.

Everything lives under CADRECOVER_HOME (default ~/.cadrecover, on the Linux/WSL
filesystem: SQLite WAL is unreliable on Windows-mounted paths like /mnt/c).

    envs/{services,cad,drawing}/   the three locked Python environments
    runtime/cadrecover.sqlite      the database
    runtime/private/<challenge>/   private challenge records + reference solids (ground truth)
    artifacts/public/<challenge>/  what miners and the public may see (drawing PNG, public record)
    wallets/                       dev wallets (local/test only) + their mnemonics (0600)
"""

from __future__ import annotations

import os
from pathlib import Path

HOME = Path(os.environ.get("CADRECOVER_HOME", Path.home() / ".cadrecover"))
ENVS = HOME / "envs"
RUNTIME = HOME / "runtime"
PRIVATE = RUNTIME / "private"
PUBLIC = HOME / "artifacts" / "public"
WALLETS = HOME / "wallets"
DB = RUNTIME / "cadrecover.sqlite"
REPO = Path(__file__).resolve().parents[2]


def env_python(env: str) -> Path:
    """Python of one of the three locked environments: services, cad, drawing."""
    return ENVS / env / "bin" / "python"


def ensure() -> None:
    for d in (RUNTIME, PRIVATE, PUBLIC, WALLETS):
        d.mkdir(parents=True, exist_ok=True)
    PRIVATE.chmod(0o700)
    WALLETS.chmod(0o700)
