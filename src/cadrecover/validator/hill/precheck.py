"""Metadata-only Hugging Face check. Never downloads weights or executes repository code."""
from __future__ import annotations

import hashlib
import re

from cadrecover.protocol.hill import ModelCommitment
from cadrecover.storage import db

MAX_WEIGHT_BYTES = 20_000_000_000
REVISION = re.compile(r"^[0-9a-fA-F]{40}$")


class PrecheckError(ValueError):
    pass


def _get(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def precheck_model(repo: str, revision: str, con=None, *, api=None) -> ModelCommitment:
    if not REVISION.fullmatch(revision):
        raise PrecheckError("revision must be a full 40-hex commit SHA; branches and tags are not accepted")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise PrecheckError("repo must be a Hugging Face owner/model identifier")
    if api is None:
        from huggingface_hub import HfApi
        api = HfApi(token=False)  # public accessibility must not depend on an operator's HF token
    try:
        info = api.model_info(repo, revision=revision, files_metadata=True)
    except Exception:
        raise PrecheckError("public repository or pinned revision not accessible") from None
    if _get(info, "private", False) or _get(info, "gated", False):
        raise PrecheckError("repository must be public and ungated")
    if str(_get(info, "sha", "")).lower() != revision.lower():
        raise PrecheckError("Hugging Face resolved a different revision")
    files = _get(info, "siblings", []) or []
    names = {_get(f, "rfilename") for f in files}
    weights = [f for f in files if str(_get(f, "rfilename", "")).endswith(".safetensors")
               and not str(_get(f, "rfilename", "")).rsplit("/", 1)[-1].startswith("adapter")]
    if not weights:
        raise PrecheckError("adapter-only repository" if "adapter_config.json" in names else "missing full safetensors weights")
    if "config.json" not in names:
        raise PrecheckError("missing config.json")
    total, lines = 0, []
    for f in weights:
        lfs = _get(f, "lfs")
        sha = _get(lfs, "sha256", "")
        size = _get(f, "size")
        if size is None:
            size = _get(lfs, "size")
        if not re.fullmatch(r"[0-9a-fA-F]{64}", str(sha)) or not isinstance(size, int) or size <= 0:
            raise PrecheckError("weight file is missing LFS SHA256 or size metadata")
        total += size
        lines.append(f"{_get(f, 'rfilename')}:{sha.lower()}")
    if total > MAX_WEIGHT_BYTES:
        raise PrecheckError(f"full weights exceed {MAX_WEIGHT_BYTES} byte one-GPU limit")
    fingerprint = hashlib.sha256("\n".join(sorted(lines)).encode("utf-8")).hexdigest()
    if con is not None:
        prior = next((m for m in db.hill_models(con) if m.fingerprint == fingerprint), None)
        if prior:
            raise PrecheckError(f"same weights as {prior.name}, committed later")
    card = _get(info, "card_data") or _get(info, "cardData")
    base = _get(card, "base_model")
    return ModelCommitment(repo=repo, revision=revision.lower(), fingerprint=fingerprint, weight_bytes=total,
                           base_model=base if isinstance(base, str) else None)
