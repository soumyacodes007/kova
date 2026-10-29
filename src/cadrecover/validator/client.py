"""Validator side of the miner protocol (owner: agent B): signed dispatch and polling."""

from __future__ import annotations

import bittensor as bt
import httpx

from cadrecover.miner.server import RESULT_PATH
from cadrecover.protocol import JobRequest, JobStatus


class MinerError(RuntimeError):
    pass


def _signed(wallet, method: str, path: str, body: bytes, miner_hotkey: str) -> dict[str, str]:
    return bt.http_auth.sign(wallet, method=method, path=path, body=body, receiver_ss58=miner_hotkey)


async def dispatch(client: httpx.AsyncClient, base_url: str, wallet, miner_hotkey: str, job: JobRequest) -> str:
    body = job.model_dump_json().encode()
    headers = {"content-type": "application/json", **_signed(wallet, "POST", "/v1/jobs", body, miner_hotkey)}
    r = await client.post(f"{base_url}/v1/jobs", content=body, headers=headers)
    if r.status_code != 202:
        raise MinerError(f"dispatch rejected ({r.status_code}): {r.text[:200]}")
    return r.json()["status"]


async def poll(client: httpx.AsyncClient, base_url: str, wallet, miner_hotkey: str, job_id: str,
               nonce_store) -> JobStatus:
    """One signed status poll; the response must be signed by the miner's hotkey and bound to us."""
    path = f"/v1/jobs/{job_id}"
    r = await client.get(f"{base_url}{path}", headers=_signed(wallet, "GET", path, b"", miner_hotkey))
    if r.status_code != 200:
        raise MinerError(f"poll failed ({r.status_code}): {r.text[:200]}")
    try:
        caller = bt.http_auth.verify(r.headers, r.content, method="POST", path=RESULT_PATH.format(job_id=job_id),
                                     self_hotkey_ss58=wallet.hotkey.ss58_address, nonce_store=nonce_store)
    except bt.http_auth.AuthError as e:
        raise MinerError(f"result signature rejected: {type(e).__name__}: {e}") from e
    if caller.hotkey_ss58 != miner_hotkey:
        raise MinerError("result signed by a different hotkey than the assigned miner")
    status = JobStatus.model_validate_json(r.content)
    if status.job_id != job_id or (status.result and status.result.job_id != job_id):
        raise MinerError("result is for a different job")
    return status
