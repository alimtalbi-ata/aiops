-- Durable one-time nonce barrier for server-signed GLPI xref events.
-- Additive only. Apply through the authorized migration process; never per request.
CREATE TABLE IF NOT EXISTS aiops.glpi_xref_consumed_nonces (
    tenant_id text NOT NULL,
    nonce text NOT NULL,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, nonce),
    CONSTRAINT glpi_xref_nonce_tenant_nonempty CHECK (length(btrim(tenant_id)) BETWEEN 1 AND 128),
    CONSTRAINT glpi_xref_nonce_value_valid CHECK (length(nonce) BETWEEN 16 AND 128)
);
CREATE INDEX IF NOT EXISTS ix_glpi_xref_consumed_nonces_expiry
    ON aiops.glpi_xref_consumed_nonces(expires_at);
