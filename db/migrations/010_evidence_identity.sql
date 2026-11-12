-- 010 — Evidence identity and atomic deduplication.
-- Both indexes are additive. If historical evidence violates uniqueness the
-- transaction intentionally fails rather than silently deleting observations.
-- payload_hash for NEW evidence hashes the full canonical observation envelope;
-- old evidence keeps its original digest and stays immutable.
create unique index if not exists ux_evidence_source_payload_hash
    on aiops.evidence(source,payload_hash);

create unique index if not exists ux_evidence_source_external_identity
    on aiops.evidence(source,external_id)
    where external_id is not null;

create index if not exists ix_evidence_run_provenance
    on aiops.evidence((provenance->>'run_id'),known_at desc)
    where provenance ? 'run_id';
