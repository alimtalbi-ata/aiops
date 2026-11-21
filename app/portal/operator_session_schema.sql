-- Proposed migration; deliberately not executed at application startup.
-- Apply using a dedicated migration owner, not the portal runtime role.
BEGIN;
CREATE TABLE IF NOT EXISTS portal_operator_sessions (
    token_digest bytea PRIMARY KEY CHECK (octet_length(token_digest) = 32),
    subject text NOT NULL CHECK (length(subject) BETWEEN 1 AND 128),
    tenant text NOT NULL CHECK (length(tenant) BETWEEN 1 AND 128),
    role text NOT NULL CHECK (role IN ('N1','N2','N3','MANAGER')),
    issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    touched_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    absolute_expires_at timestamptz NOT NULL,
    CHECK (touched_at >= issued_at),
    CHECK (absolute_expires_at > issued_at)
);
CREATE INDEX IF NOT EXISTS portal_operator_sessions_expiry_idx
    ON portal_operator_sessions (absolute_expires_at);
CREATE INDEX IF NOT EXISTS portal_operator_sessions_subject_idx
    ON portal_operator_sessions (subject, tenant);
REVOKE ALL ON portal_operator_sessions FROM PUBLIC;
COMMIT;
