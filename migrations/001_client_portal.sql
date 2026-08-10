BEGIN;

CREATE TABLE IF NOT EXISTS client_portal_access (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL UNIQUE
        REFERENCES clients(id)
        ON DELETE CASCADE,
    access_token TEXT NOT NULL UNIQUE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client_action_daily_logs (
    id BIGSERIAL PRIMARY KEY,
    client_id INTEGER NOT NULL
        REFERENCES clients(id)
        ON DELETE CASCADE,
    action_id INTEGER NOT NULL
        REFERENCES client_actions(id)
        ON DELETE CASCADE,
    tracked_on DATE NOT NULL,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (action_id, tracked_on)
);

COMMIT;
