-- F3 distributed rate limiting for public unauthenticated endpoints.
-- Raw source keys are never stored; the application persists SHA-256 digests only.

CREATE TABLE IF NOT EXISTS campaia_runtime.rate_limit_windows (
    scope TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    window_started_at TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL CHECK (request_count >= 0),
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (scope, key_hash)
);
