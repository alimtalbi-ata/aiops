create unique index if not exists ux_evidence_idempotency on aiops.evidence((provenance->>'idempotency_key')) where provenance ? 'idempotency_key';
