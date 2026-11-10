-- Optional, NOT applied automatically. Requires authorized schema migration.
-- Signed GLPI xref replay barrier; unique tenant+nonce insert is atomic.
CREATE SCHEMA IF NOT EXISTS aiops;
CREATE TABLE IF NOT EXISTS aiops.glpi_xref_consumed_nonces (
    tenant_id text NOT NULL,
    nonce text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, nonce)
);
-- Do not prune nonces until signed-event validity plus clock skew has elapsed.
-- Do not grant HTTP/browser roles INSERT/DELETE on this table.
