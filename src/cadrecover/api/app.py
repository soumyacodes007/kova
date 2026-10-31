"""The read API (owner: agent C). `create_app()` -> FastAPI; `main()` serves it on 127.0.0.1:8000.

    uvicorn cadrecover.api.app:create_app --factory --host 127.0.0.1 --port 8000
    python -m cadrecover.api.app [--db PATH] [--host 127.0.0.1] [--port 8000]

Read-only and honest: every number comes from SQLite or the public artifact folders. While a challenge is
active, hidden-edit values, failed-check text and reference models are withheld (they are ground truth).
"""

from __future__ import annotations

from typing import Literal

import argparse
import os
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.routing import APIRoute

from cadrecover import paths
from cadrecover.api import chain_info, events, hill, queries
from cadrecover.api.db_access import connect_ro
from cadrecover.api.models import (
    AuditOut,
    ChallengeOut,
    CommitmentOut,
    EventsPage,
    Health,
    Leaderboard,
    MinerDetail,
    RunDetail,
    RunStatus,
    RunSummary,
    StatusOut,
    WeightBatchOut,
)
from cadrecover.protocol import CAD_ENGINE, PROTOCOL_VERSION, QUALITY_FLOOR, SCORING_VERSION
from cadrecover.storage import db

API_VERSION = "0.1.0"
DEFAULT_CORS = ["http://localhost:3000"]
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")  # challenge and run ids; no dots or slashes
HOTKEY_RE = re.compile(r"^[A-Za-z0-9]{1,64}$")
SSE_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no", "Connection": "keep-alive"}


def _unique_id(route: APIRoute) -> str:
    return route.name  # operationIds become the generated TypeScript operation names


def _inside(root: Path, *parts: str) -> Path | None:
    """root/parts resolved, only if it is a regular file strictly inside root (symlinks included)."""
    base = root.resolve()
    target = base.joinpath(*parts).resolve()
    return target if base in target.parents and target.is_file() else None


def create_app(db_path: Path | str | None = None, *, public_dir: Path | None = None, runs_dir: Path | None = None,
               state_file: Path | None = None, chain_rpc: str | None = "auto", cors_origins: list[str] | None = None,
               sse_poll_s: float = 0.5, sse_keepalive_s: float = 15.0,
               hill_dir: Path | None = None, hill_network: str | None = None) -> FastAPI:
    """Build the app.

    chain_rpc: "auto" probes the local node named in chain.json; None never touches the chain; or an HTTP RPC URL.
    """
    db_file = Path(db_path or paths.DB)
    db.connect(db_file).close()  # make sure the file and schema exist; the API itself only reads
    public_root = Path(public_dir or paths.PUBLIC)
    runs_root = Path(runs_dir or (paths.RUNTIME / "runs"))
    hill_root = Path(hill_dir or (paths.RUNTIME / "hill"))
    hill_network = hill_network or os.environ.get("CADRECOVER_API_NETWORK", "local")
    if hill_network not in ("local", "test"):
        raise ValueError("CADRECOVER_API_NETWORK must be local or test")
    probe = chain_info.ChainProbe(state_file if state_file is not None else chain_info.default_state_file(hill_network), chain_rpc)
    if cors_origins is None:
        env = os.environ.get("CADRECOVER_API_CORS")
        cors_origins = [o.strip() for o in env.split(",") if o.strip()] if env else DEFAULT_CORS

    app = FastAPI(
        title="CADRecover read API", version=API_VERSION, generate_unique_id_function=_unique_id,
        description="Read-only JSON, resumable Server-Sent Events and public artifacts for the CADRecover validator. "
                    "Nothing here is invented: empty lists mean nothing has happened yet.")
    app.state.db_path = db_file
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_methods=["GET", "HEAD", "OPTIONS"],
                       allow_headers=["Last-Event-ID", "Accept", "Cache-Control", "Content-Type"])

    def get_con() -> Iterator:
        con = connect_ro(db_file)
        try:
            yield con
        finally:
            con.close()

    Con = Depends(get_con)

    # ---------------------------------------------------------------- status

    @app.get("/v1/health", response_model=Health, tags=["status"])
    def health(con=Con):
        con.execute("SELECT 1 FROM schema_version LIMIT 1")
        return Health(ok=True, db=db_file.name)

    @app.get("/v1/status", response_model=StatusOut, tags=["status"])
    def status(con=Con):
        return StatusOut(
            protocol_version=PROTOCOL_VERSION, scoring_version=SCORING_VERSION, cad_engine=dict(CAD_ENGINE),
            quality_floor=QUALITY_FLOOR, server_time=datetime.now(timezone.utc).isoformat(), chain=probe.info(),
            counts=queries.counts(con), latest_event_id=queries.latest_event_id(con), latest_run=queries.latest_run(con))

    # ---------------------------------------------------------------- runs and challenges

    @app.get("/v1/hill", response_model=hill.Hill, tags=["hill"])
    def get_hill(con=Con):
        return hill.hill(con, hill_network)

    @app.get("/v1/models", response_model=list[hill.Model], tags=["hill"])
    def list_hill_models(network: Literal["local", "test"] | None = None, con=Con):
        return hill.models(con, network or hill_network)

    @app.get("/v1/models/{fingerprint}", response_model=hill.ModelDetail, tags=["hill"])
    def get_hill_model(fingerprint: str, con=Con):
        found = hill.model_detail(con, fingerprint, hill_network) if ID_RE.fullmatch(fingerprint) else None
        if found is None:
            raise HTTPException(404, "unknown model")
        return found

    @app.get("/v1/matches", response_model=list[hill.MatchSummary], tags=["hill"])
    def list_hill_matches(con=Con):
        return hill.matches(con, hill_network)

    @app.get("/v1/matches/{match_id}", response_model=hill.MatchDetail, tags=["hill"])
    def get_hill_match(match_id: str, con=Con):
        found = hill.match_detail(con, match_id, hill_root, hill_network) if ID_RE.fullmatch(match_id) else None
        if found is None:
            raise HTTPException(404, "unknown match")
        return found

    @app.get("/v1/runs", response_model=list[RunSummary], tags=["runs"])
    def list_runs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
                  status: RunStatus | None = None, con=Con):
        return queries.runs(con, limit=limit, offset=offset, status=status)

    @app.get("/v1/runs/{run_id}", response_model=RunDetail, tags=["runs"])
    def get_run(run_id: str, con=Con):
        found = queries.run_detail(con, run_id, runs_root) if ID_RE.match(run_id) else None
        if found is None:
            raise HTTPException(404, "unknown run")
        return found

    @app.get("/v1/challenges/{challenge_id}", response_model=ChallengeOut, tags=["runs"])
    def get_challenge(challenge_id: str, con=Con):
        found = queries.challenge(con, challenge_id) if ID_RE.match(challenge_id) else None
        if found is None:
            raise HTTPException(404, "unknown challenge")
        return found

    # ---------------------------------------------------------------- standings, miners, chain records

    @app.get("/v1/leaderboard", response_model=Leaderboard, tags=["standings"])
    def leaderboard(con=Con):
        return queries.leaderboard(con)

    @app.get("/v1/miners/{hotkey}", response_model=MinerDetail, tags=["standings"])
    def get_miner(hotkey: str, con=Con):
        found = queries.miner_detail(con, hotkey) if HOTKEY_RE.match(hotkey) else None
        if found is None:
            raise HTTPException(404, "unknown miner")
        return found

    @app.get("/v1/weights", response_model=list[WeightBatchOut], tags=["chain"])
    def weights(limit: int = Query(50, ge=1, le=500), con=Con):
        return queries.weight_batches(con, limit=limit)

    @app.get("/v1/commitments", response_model=list[CommitmentOut], tags=["chain"])
    def list_commitments(con=Con):
        return queries.commitments(con)

    @app.get("/v1/audits", response_model=list[AuditOut], tags=["chain"])
    def list_audits(limit: int = Query(100, ge=1, le=500), hotkey: str | None = None, con=Con):
        return queries.audits(con, hotkey=hotkey, limit=limit)

    # ---------------------------------------------------------------- public files (read-only)

    png = {200: {"content": {"image/png": {}}, "description": "The drawing PNG"}}
    glb = {200: {"content": {"model/gltf-binary": {}}, "description": "A GLB mesh written by the validator"}}

    @app.get("/v1/matches/{match_id}/tasks/{index}/{side}/models/{name}", response_class=FileResponse,
             responses=glb, tags=["files"])
    def hill_model_file(match_id: str, index: int, side: str, name: str, con=Con):
        if not ID_RE.fullmatch(match_id) or not hill.model_path_allowed(con, match_id, index, side, name, hill_network):
            raise HTTPException(404, "no such model, or not yet public")
        f = _inside(hill_root, match_id, f"task{index}", side, name)
        if f is None:
            raise HTTPException(404, "no such model")
        return FileResponse(f, media_type="model/gltf-binary", headers={"Cache-Control": "public, max-age=60"})

    @app.get("/v1/challenges/{challenge_id}/drawing.png", response_class=FileResponse, responses=png, tags=["files"])
    def drawing(challenge_id: str, con=Con):
        if not ID_RE.match(challenge_id) or queries.challenge(con, challenge_id) is None:
            raise HTTPException(404, "unknown challenge")
        f = _inside(public_root, challenge_id, "drawing.png")
        if f is None:
            raise HTTPException(404, "no drawing")
        return FileResponse(f, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/v1/runs/{run_id}/miners/{uid}/models/{name}", response_class=FileResponse, responses=glb, tags=["files"])
    def model(run_id: str, uid: int, name: str, con=Con):
        """`s<0-3>.candidate.glb` once the miner is evaluated; `s<0-3>.reference.glb` only after the challenge retires."""
        if not ID_RE.match(run_id) or not queries.model_path_allowed(con, run_id, uid, name):
            raise HTTPException(404, "no such model, or not yet public")
        f = _inside(runs_root, run_id, f"uid{uid}", name)
        if f is None:
            raise HTTPException(404, "no such model")
        return FileResponse(f, media_type="model/gltf-binary", headers={"Cache-Control": "public, max-age=60"})

    # ---------------------------------------------------------------- events

    @app.get("/v1/events", response_model=EventsPage, tags=["events"])
    def list_events(after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000), run_id: str | None = None,
                    kind: str | None = Query(None, description="exact kind, or a prefix such as `weights`"), con=Con):
        found = queries.events(con, after=after, limit=limit, run_id=run_id, kind=kind)
        return EventsPage(events=found, next_after=found[-1].event_id if found else after,
                          latest_event_id=queries.latest_event_id(con))

    sse = {200: {"content": {"text/event-stream": {"schema": {"type": "string"}}},
                 "description": "SSE. Each message: `id: <event_id>` and `data: <EventOut JSON>`"}}

    @app.get("/v1/events/stream", response_class=StreamingResponse, responses=sse, tags=["events"])
    async def stream_events(
        request: Request,
        after: int | None = Query(None, ge=0, description="replay events newer than this id; omit to receive only "
                                                         "new events; 0 replays everything"),
        run_id: str | None = None,
        kind: str | None = Query(None, description="exact kind, or a prefix such as `job`"),
        limit: int | None = Query(None, ge=1, description="close after this many events (for scripts and tests)"),
        last_event_id: str | None = Header(None, alias="Last-Event-ID",
                                           description="set by EventSource on reconnect; wins over `after`"),
    ):
        cursor = events.parse_cursor(last_event_id)
        if cursor is None:
            cursor = after
        if cursor is None:  # live tail: start at the newest event
            con = connect_ro(db_file)
            try:
                cursor = queries.latest_event_id(con)
            finally:
                con.close()
        gen = events.event_stream(lambda: connect_ro(db_file), cursor=cursor, run_id=run_id, kind=kind, limit=limit,
                                  poll_s=sse_poll_s, keepalive_s=sse_keepalive_s, is_disconnected=request.is_disconnected)
        return StreamingResponse(gen, media_type="text/event-stream", headers=SSE_HEADERS)

    return app


def main(argv: list[str] | None = None) -> None:
    import uvicorn

    p = argparse.ArgumentParser(prog="cadrecover-api", description="Serve the CADRecover read API")
    p.add_argument("--host", default="127.0.0.1", help="bind address (default loopback)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--db", default=None, help="SQLite path (default ~/.cadrecover/runtime/cadrecover.sqlite)")
    p.add_argument("--no-chain", action="store_true", help="never probe the chain for the head block")
    a = p.parse_args(argv)
    app = create_app(a.db, chain_rpc=None if a.no_chain else "auto")
    uvicorn.run(app, host=a.host, port=a.port, log_level="info")


if __name__ == "__main__":
    main()
