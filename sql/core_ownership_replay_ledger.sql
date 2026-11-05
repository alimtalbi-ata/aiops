-- Core #233: explicit PG16 installation; NOT auto-applied or a LIVE mutation.
-- Keep consumed keys indefinitely unless retention is separately approved.
-- Replay identity must not be recycled merely because a proof expired.
CREATE TABLE IF NOT EXISTS core_ownership_replay_ledger (
    issuer text NOT NULL CHECK (length(issuer) > 0),
    jti text NOT NULL CHECK (length(jti) > 0),
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (issuer, jti)
);
-- Provision a least-privilege INSERT/SELECT role separately. Never GRANT to Portal.
