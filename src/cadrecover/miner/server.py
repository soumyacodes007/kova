"""Miner HTTP server (owner: agent C). Bittensor v11 has no Axon: this is our own FastAPI app.

  POST /v1/jobs            signed by the validator  -> 202 + JobAccepted (idempotent by job_id)
  GET  /v1/jobs/{job_id}   signed by the validator  -> JobStatus, response signed by this miner's hotkey
  GET  /v1/health          unsigned                 -> availability and protocol version

Requests are verified with bittensor.http_auth (receiver binding, freshness,
signature, replay). Responses carry a signature over the body made as a
"POST /v1/results/{job_id}" payload bound to the validator, so the validator can
verify who produced a result. A signature proves the sender, not correctness.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import datetime, timezone

import bittensor as bt
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from cadrecover.miner.strategies import Strategy
from cadrecover.protocol import PROTOCOL_VERSION, JobAccepted, JobRequest, JobResult, JobStatus

RESULT_PATH = "/v1/results/{job_id}"
MAX_REQUEST_BYTES = 256 * 1024


def _target(request: Request) -> str:
    return request.url.path + (f"?{request.url.query}" if request.url.query else "")


async def _http_fetch(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30) as client:
        return (await client.get(url)).raise_for_status().content


def create_app(wallet, strategy: Strategy, *, allowed_validators: set[str] | None = None,
               fetch_drawing=_http_fetch) -> FastAPI:
    """`allowed_validators`: hotkeys allowed to send jobs (None = any validly signed caller; Phase 6 uses the metagraph)."""
    app = FastAPI(title=f"cadrecover miner ({strategy.name})")
    hotkey = wallet.hotkey.ss58_address
    nonces = bt.http_auth.InMemoryNonceStore()
    jobs: dict[str, JobStatus] = {}
    owners: dict[str, str] = {}  # job_id -> validator hotkey that created it

    async def authenticate(request: Request, body: bytes):
        try:
            caller = bt.http_auth.verify(request.headers, body, method=request.method, path=_target(request),
                                         self_hotkey_ss58=hotkey, nonce_store=nonces)
        except bt.http_auth.AuthError as e:
            return None, JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=401)
        if allowed_validators is not None and caller.hotkey_ss58 not in allowed_validators:
            return None, JSONResponse({"error": "caller is not an allowed validator"}, status_code=403)
        return caller, None

    async def run_job(job: JobRequest) -> None:
        jobs[job.job_id] = JobStatus(job_id=job.job_id, status="running")
        t0 = time.monotonic()
        try:
            png = await fetch_drawing(job.drawing_url)
            if hashlib.sha256(png).hexdigest() != job.challenge.drawing.sha256:
                raise ValueError("drawing hash does not match the challenge record")
            sol = await asyncio.to_thread(strategy.solve, job.challenge, png, job.job_id)
            result = JobResult.for_source(job_id=job.job_id, challenge_id=job.challenge.challenge_id,
                                          source=sol.source, model_id=sol.model_id,
                                          strategy_version=f"{strategy.name}/{sol.strategy_version}",
                                          duration_s=time.monotonic() - t0)
            jobs[job.job_id] = JobStatus(job_id=job.job_id, status="done", result=result)
        except Exception as e:  # noqa: BLE001 - incl. StrategyUnavailable: report it, don't crash the server
            jobs[job.job_id] = JobStatus(job_id=job.job_id, status="failed", error=f"{type(e).__name__}: {e}")

    @app.get("/v1/health")
    async def health():
        return {"status": "ok", "protocol_version": PROTOCOL_VERSION, "hotkey": hotkey,
                "strategy": strategy.name, "kind": strategy.kind, "time": datetime.now(timezone.utc).isoformat()}

    @app.post("/v1/jobs")
    async def submit(request: Request):
        body = await request.body()
        if len(body) > MAX_REQUEST_BYTES:
            return JSONResponse({"error": "request too large"}, status_code=413)
        caller, err = await authenticate(request, body)
        if err:
            return err
        job = JobRequest.model_validate_json(body)
        if job.job_id in jobs:  # idempotent retry: never a second model run
            return JSONResponse(JobAccepted(job_id=job.job_id, status=jobs[job.job_id].status).model_dump(),
                                status_code=202)
        owners[job.job_id] = caller.hotkey_ss58
        jobs[job.job_id] = JobStatus(job_id=job.job_id, status="queued")
        asyncio.get_running_loop().create_task(run_job(job))
        return JSONResponse(JobAccepted(job_id=job.job_id, status="queued").model_dump(), status_code=202)

    @app.get("/v1/jobs/{job_id}")
    async def status(job_id: str, request: Request):
        caller, err = await authenticate(request, b"")
        if err:
            return err
        if job_id not in jobs or owners.get(job_id) != caller.hotkey_ss58:
            return JSONResponse({"error": "unknown job"}, status_code=404)
        payload = jobs[job_id].model_dump_json().encode()
        headers = bt.http_auth.sign(wallet, method="POST", path=RESULT_PATH.format(job_id=job_id), body=payload,
                                    receiver_ss58=caller.hotkey_ss58)
        return Response(content=payload, media_type="application/json", headers=headers)

    return app
