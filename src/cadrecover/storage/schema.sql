-- CADRecover SQLite schema (owner: agent B). WAL mode; one host.
-- Ground truth stays in runtime/private/<challenge>/ files; this DB only points at it.

CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS challenges (
    challenge_id   TEXT PRIMARY KEY,
    family         TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'retired')),
    public_json    TEXT NOT NULL,          -- PublicChallenge
    private_path   TEXT NOT NULL,          -- runtime/private/<id>/private.json (never served while active)
    retired_at     TEXT
);

-- Miner identity is hotkey + registration block: a recycled UID starts fresh.
CREATE TABLE IF NOT EXISTS miners (
    hotkey               TEXT NOT NULL,
    registered_at_block  INTEGER NOT NULL,
    uid                  INTEGER NOT NULL,
    first_seen           TEXT NOT NULL,
    label                TEXT,             -- e.g. 'strategy-3' or 'diagnostic:constant'
    PRIMARY KEY (hotkey, registered_at_block)
);

CREATE TABLE IF NOT EXISTS runs (
    run_id         TEXT PRIMARY KEY,
    challenge_id   TEXT NOT NULL REFERENCES challenges (challenge_id),
    started_at     TEXT NOT NULL,
    deadline_at    TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('dispatching', 'collecting', 'evaluating', 'done', 'aborted'))
);

CREATE TABLE IF NOT EXISTS assignments (
    job_id               TEXT PRIMARY KEY,  -- idempotent: retries reuse it
    run_id               TEXT NOT NULL REFERENCES runs (run_id),
    miner_hotkey         TEXT NOT NULL,
    registered_at_block  INTEGER NOT NULL,
    uid                  INTEGER NOT NULL,
    sent_at              TEXT,
    status               TEXT NOT NULL CHECK (status IN ('pending', 'sent', 'done', 'failed', 'timeout')),
    UNIQUE (run_id, miner_hotkey)
);

CREATE TABLE IF NOT EXISTS submissions (
    job_id         TEXT PRIMARY KEY REFERENCES assignments (job_id),
    received_at    TEXT NOT NULL,
    source_sha256  TEXT NOT NULL,
    envelope_json  TEXT NOT NULL           -- JobResult (source included; size-capped by the protocol)
);

CREATE TABLE IF NOT EXISTS evaluations (
    job_id          TEXT PRIMARY KEY REFERENCES assignments (job_id),
    challenge_id    TEXT NOT NULL,
    miner_hotkey    TEXT NOT NULL,
    quality         REAL,                  -- Q; NULL for validator outages (excluded for everyone)
    failure_class   TEXT NOT NULL CHECK (failure_class IN ('none', 'miner', 'validator_outage')),
    failure_reason  TEXT,
    evaluation_json TEXT NOT NULL,         -- Evaluation
    evaluated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluation_sets (
    job_id        TEXT NOT NULL REFERENCES evaluations (job_id),
    set_index     INTEGER NOT NULL CHECK (set_index BETWEEN 0 AND 3),
    valid         INTEGER NOT NULL,
    critical_ok   INTEGER NOT NULL,
    geometry      REAL NOT NULL,
    dimensions    REAL NOT NULL,
    q             REAL NOT NULL,
    failed_checks TEXT NOT NULL DEFAULT '[]',
    PRIMARY KEY (job_id, set_index)
);

-- Append-only event log; event_id is the SSE resume cursor.
CREATE TABLE IF NOT EXISTS events (
    event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    at         TEXT NOT NULL,
    kind       TEXT NOT NULL,
    run_id     TEXT,
    payload    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS weight_batches (
    batch_id         TEXT PRIMARY KEY,
    network          TEXT NOT NULL CHECK (network IN ('local', 'test')),
    netuid           INTEGER NOT NULL,
    validator_hotkey TEXT NOT NULL,
    floor            REAL NOT NULL,
    batch_json       TEXT NOT NULL,        -- WeightBatch
    created_at       TEXT NOT NULL
);

-- Commit, reveal and incentive are separate states: one row per transition.
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id    TEXT NOT NULL REFERENCES weight_batches (batch_id),
    state       TEXT NOT NULL,
    block       INTEGER,
    extrinsic   TEXT,
    readback    TEXT,
    error       TEXT,
    at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS commitments (
    hotkey               TEXT NOT NULL,
    registered_at_block  INTEGER NOT NULL,
    engine_digest        TEXT NOT NULL,
    strategy_version     TEXT,
    block                INTEGER NOT NULL,
    PRIMARY KEY (hotkey, registered_at_block, block)
);

CREATE TABLE IF NOT EXISTS audits (
    audit_id       TEXT PRIMARY KEY,
    miner_hotkey   TEXT NOT NULL,
    engine_digest  TEXT NOT NULL,
    challenge_id   TEXT NOT NULL,
    quality        REAL,
    passed         INTEGER NOT NULL,
    block          INTEGER,
    at             TEXT NOT NULL,
    detail         TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS events_run ON events (run_id, event_id);
CREATE INDEX IF NOT EXISTS evaluations_miner ON evaluations (miner_hotkey, evaluated_at);
