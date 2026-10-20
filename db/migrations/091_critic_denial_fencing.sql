BEGIN;

ALTER TABLE aiops.critic_denial_outbox
  ADD COLUMN IF NOT EXISTS lease_owner text,
  ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz,
  ADD COLUMN IF NOT EXISTS fencing_token bigint NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS critic_denial_claim_idx
  ON aiops.critic_denial_outbox(lease_expires_at,created_at)
  WHERE status='PENDING';

COMMIT;
