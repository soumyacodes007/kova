"""Miner HTTP protocol: signed jobs, signed results, idempotency and the attacks PRD §Verification lists."""

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

import bittensor as bt
import httpx
import pytest

from cadrecover.miner.server import create_app
from cadrecover.miner.strategies import Solution, Strategy
from cadrecover.protocol import Artifact, JobRequest, ParameterSpec, PublicChallenge
from cadrecover.validator import client as vclient

PNG = b"\x89PNG fake drawing bytes"


class CountingStrategy(Strategy):
    name, kind = "test-fixed", "diagnostic"

    def __init__(self):
        self.calls = 0

    def solve(self, challenge, drawing_png, job_id):
        self.calls += 1
        return Solution("def build_part(overrides):\n    return None\n", model_id="test", strategy_version="0")


@pytest.fixture(scope="module")
def wallets(tmp_path_factory):
    path = str(tmp_path_factory.mktemp("wallets"))
    make = lambda n: bt.wallets.create(n, "default", path=path, use_password=False, on_mnemonic=lambda *a: None)  # noqa: E731
    return make("validator"), make("miner"), make("other")


def _job(job_id="job-1", sha=None):
    ch = PublicChallenge(
        challenge_id="ch_test", family="plate", frame="f",
        parameters=[ParameterSpec(name="width", description="X", min=1, max=2)], edit_rules=[], critical_features=[],
        drawing=Artifact(path="ch_test/drawing.png", sha256=sha or hashlib.sha256(PNG).hexdigest(), media_type="image/png"),
    )
    return JobRequest(job_id=job_id, challenge=ch, drawing_url="http://drawings/ch_test/drawing.png",
                      deadline_at=datetime.now(timezone.utc) + timedelta(minutes=3))


def _run(coro):
    return asyncio.run(coro)


def _client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://miner")


async def _fetch(url):
    return PNG


async def _wait_done(c, validator, miner_hk, job_id, store):
    for _ in range(100):
        st = await vclient.poll(c, "http://miner", validator, miner_hk, job_id, store)
        if st.status in ("done", "failed"):
            return st
        await asyncio.sleep(0.02)
    raise AssertionError("job never finished")


def test_signed_job_round_trip_and_signed_result(wallets):
    validator, miner, _ = wallets
    strat = CountingStrategy()
    app = create_app(miner, strat, fetch_drawing=_fetch)

    async def go():
        async with _client(app) as c:
            store = bt.http_auth.InMemoryNonceStore()
            assert await vclient.dispatch(c, "http://miner", validator, miner.hotkey.ss58_address, _job()) == "queued"
            st = await _wait_done(c, validator, miner.hotkey.ss58_address, "job-1", store)
            assert st.status == "done", st.error
            assert st.result.source_sha256 == hashlib.sha256(st.result.source.encode()).hexdigest()
            # idempotent retry (fresh signature) never runs the model twice
            assert await vclient.dispatch(c, "http://miner", validator, miner.hotkey.ss58_address, _job()) == "done"
            assert strat.calls == 1
    _run(go())


def test_drawing_hash_mismatch_fails_the_job(wallets):
    validator, miner, _ = wallets
    app = create_app(miner, CountingStrategy(), fetch_drawing=_fetch)

    async def go():
        async with _client(app) as c:
            store = bt.http_auth.InMemoryNonceStore()
            await vclient.dispatch(c, "http://miner", validator, miner.hotkey.ss58_address, _job("j2", sha="0" * 64))
            st = await _wait_done(c, validator, miner.hotkey.ss58_address, "j2", store)
            assert st.status == "failed" and "hash" in st.error
    _run(go())


@pytest.mark.parametrize("attack", ["unsigned", "tampered", "wrong_receiver", "replay", "stale", "oversized"])
def test_bad_requests_are_rejected(wallets, attack):
    validator, miner, other = wallets
    app = create_app(miner, CountingStrategy(), fetch_drawing=_fetch)
    body = _job(f"job-{attack}").model_dump_json().encode()

    async def go():
        async with _client(app) as c:
            receiver = other.hotkey.ss58_address if attack == "wrong_receiver" else miner.hotkey.ss58_address
            payload = body
            if attack == "oversized":  # signed correctly, but larger than MAX_REQUEST_BYTES
                payload = body[:-1] + b',"padding":"' + b"x" * 300_000 + b'"}'
            sent = payload
            nonce = (int(datetime.now(timezone.utc).timestamp()) - 120) * 10**9 if attack == "stale" else None
            headers = bt.http_auth.sign(validator, method="POST", path="/v1/jobs", body=payload,
                                        receiver_ss58=receiver, nonce_ns=nonce)
            if attack == "unsigned":
                headers = {}
            if attack == "tampered":
                sent = payload.replace(b"job-", b"JOB-")
            r = await c.post("/v1/jobs", content=sent, headers=headers)
            if attack == "replay":
                assert r.status_code == 202
                r = await c.post("/v1/jobs", content=sent, headers=headers)
            assert r.status_code == (413 if attack == "oversized" else 401), (attack, r.text)
    _run(go())


def test_other_validator_cannot_read_someone_elses_job(wallets):
    validator, miner, other = wallets
    app = create_app(miner, CountingStrategy(), fetch_drawing=_fetch)

    async def go():
        async with _client(app) as c:
            await vclient.dispatch(c, "http://miner", validator, miner.hotkey.ss58_address, _job("j3"))
            with pytest.raises(vclient.MinerError, match="404"):
                await vclient.poll(c, "http://miner", other, miner.hotkey.ss58_address, "j3",
                                   bt.http_auth.InMemoryNonceStore())
    _run(go())


def test_allowlist_blocks_unknown_validators(wallets):
    validator, miner, other = wallets
    app = create_app(miner, CountingStrategy(), fetch_drawing=_fetch,
                     allowed_validators={validator.hotkey.ss58_address})

    async def go():
        async with _client(app) as c:
            with pytest.raises(vclient.MinerError, match="403"):
                await vclient.dispatch(c, "http://miner", other, miner.hotkey.ss58_address, _job("j4"))
    _run(go())
