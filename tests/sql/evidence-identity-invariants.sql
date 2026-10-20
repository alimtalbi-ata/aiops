-- Integration assertions for atomic evidence identity and append-only semantics.
-- Run only against an isolated/disposable qualification database.
insert into aiops.evidence(
    evidence_id,source,external_id,claim,confidence,provenance,payload_hash,payload
) values (
    'CI-EVIDENCE-IDENTITY-A','ci-evidence-identity','ci-external-A',
    'Synthetic qualification observation',0.95,'{"synthetic":true}'::jsonb,
    'ci-identity-full-hash-A','{"metric":"paths","active":1}'::jsonb
);

do $$
begin
  begin
    insert into aiops.evidence(
        evidence_id,source,external_id,claim,confidence,provenance,payload_hash,payload
    ) values (
        'CI-EVIDENCE-CONFLICT-EXTERNAL','ci-evidence-identity','ci-external-A',
        'Changed observation under same external identity',0.95,
        '{"synthetic":true}'::jsonb,'ci-identity-changed-hash',
        '{"metric":"paths","active":2}'::jsonb
    );
    raise exception 'FAIL|same_source_external_id_accepted';
  exception when unique_violation then
    raise notice 'PASS|source_external_identity_constraint';
  end;
  begin
    insert into aiops.evidence(
        evidence_id,source,external_id,claim,confidence,provenance,payload_hash,payload
    ) values (
        'CI-EVIDENCE-CONFLICT-DIGEST','ci-evidence-identity','ci-external-B',
        'Different ID but reused canonical envelope digest',0.95,
        '{"synthetic":true}'::jsonb,'ci-identity-full-hash-A',
        '{"metric":"paths","active":1}'::jsonb
    );
    raise exception 'FAIL|same_source_full_digest_accepted';
  exception when unique_violation then
    raise notice 'PASS|source_envelope_digest_constraint';
  end;
  begin
    update aiops.evidence set claim='illegal mutation'
    where evidence_id='CI-EVIDENCE-IDENTITY-A';
    raise exception 'FAIL|evidence_was_mutable';
  exception when raise_exception then
    if sqlerrm not like '%append-only record%' then raise; end if;
    raise notice 'PASS|immutable_evidence';
  end;
end $$;

-- Identical canonical data may legitimately come from different source authorities.
insert into aiops.evidence(
    evidence_id,source,external_id,claim,confidence,provenance,payload_hash,payload
) values (
    'CI-EVIDENCE-IDENTITY-OTHER-SOURCE','ci-evidence-other-source','ci-external-A',
    'Synthetic qualification observation',0.95,'{"synthetic":true}'::jsonb,
    'ci-identity-full-hash-A','{"metric":"paths","active":1}'::jsonb
);

do $$
begin
  if (select count(*) from aiops.evidence where evidence_id in
      ('CI-EVIDENCE-IDENTITY-A','CI-EVIDENCE-IDENTITY-OTHER-SOURCE')) <> 2 then
    raise exception 'FAIL|source_scoping_not_preserved';
  end if;
  raise notice 'PASS|separate_evidence_authorities';
end $$;
