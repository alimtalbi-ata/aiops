"""INT08B offline transport-neutral admission seam; never authenticates a peer."""
from copy import deepcopy
from typing import Protocol
from datetime import timedelta
from .acme_runtime_context import digest, _utc, _id, RECEIPT
from worker.acme_simulated_hitl import decode_authority_json

ROLES = ('core','twin','policy','history','postcheck','terminal')
READ_SEQUENCE = ('core','twin','policy','core','history','postcheck','terminal','terminal')
REGISTRY_SCHEMA = 'aiops.int08.authority-registry.v1'
ENVELOPE_SCHEMA = 'aiops.int08.authority-envelope.v1'

class AuthorityReader(Protocol):
    def __call__(self, request: dict) -> tuple[bytes, dict | None]:
        """Return opaque JSON and separate transport observation; no credentials."""

def inspect_authority_batch(expected, intent, registry, requests, observations, *, as_of_utc):
    """Pure structural preflight. Transport metadata is injected, not verified.

    requests are caller-owned one-use challenges; observations are (bytes, metadata)
    in READ_SEQUENCE. C owns collection; B V4 remains the business validator.
    """
    def stop(reason, reject=False):
        return dict(qualification='REJECT' if reject else 'BLOCK', reason=reason,
                    binding_status='UNBOUND',runtime_freshness='UNKNOWN',
                    runtime_attested=False,live_remediation_authorized=False,
                    transport_authenticated=False,admitted_to_runtime=False)
    try:
        expected,intent,registry,requests,observations=deepcopy(
            (expected,intent,registry,requests,observations))
        now=_utc(as_of_utc)
        identity={k:intent[k] for k in RECEIPT}
        identity['impact_incident_id']=expected['impact_incident_id']
        if (not all(_id(v) for v in identity.values())
                or identity['tenant_id']!='ACME-TEST'
                or any(expected[k]!=identity[k] for k in ('tenant_id','incident_id','run_id','attempt_id'))
                or identity['incident_id']==identity['impact_incident_id']
                or identity['run_id'].startswith(('SIM-ACME-','ACME-SIM-'))
                or not _id(expected['snapshot_id'])):
            return stop('IDENTITY_INVALID',True)
        if registry is None or requests is None or observations is None:
            return stop('EVIDENCE_MISSING')
        if registry.get('schema')!=REGISTRY_SCHEMA or set(registry['authorities'])!=set(ROLES):
            return stop('REGISTRY_INVALID',True)
        entries=registry['authorities']
        if len({entries[k]['source_id'] for k in ROLES})!=len(ROLES):
            return stop('SOURCE_COLLISION',True)
        if len({entries[k]['principal'] for k in ROLES})!=len(ROLES):
            return stop('PRINCIPAL_COLLISION',True)
        for role in ROLES:
            e=entries[role]
            if type(e.get('max_age_seconds')) is not int or e['max_age_seconds']<0:
                return stop('FRESHNESS_POLICY_MISSING')
            if e.get('revocation_state')!='ACTIVE':
                return stop('SOURCE_REVOKED_OR_UNKNOWN')
            if e.get('tenant_id')!=identity['tenant_id']:
                return stop('REGISTRY_TENANT_MISMATCH',True)
        if len(requests)!=len(READ_SEQUENCE) or len(observations)!=len(READ_SEQUENCE):
            return stop('EVIDENCE_MISSING')
        challenges=set()
        stable={}
        phases=[]
        for role,request,observation in zip(READ_SEQUENCE,requests,observations):
            entry=entries[role]
            challenge=request['challenge']
            if not _id(challenge) or challenge in challenges:
                return stop('REPLAY',True)
            challenges.add(challenge)
            if request['role']!=role or request['identity']!=identity:
                return stop('REQUEST_BINDING',True)
            if observation is None:
                return stop('SOURCE_MISSING')
            raw,meta=observation
            row=decode_authority_json(raw)
            if type(row) is not dict or set(row)!={
                'schema','role','source_id','classification','identity','snapshot_id',
                'parent_snapshot_id','version','observed_at','content','content_sha256'}:
                return stop('ENVELOPE_SHAPE',True)
            if row['schema']!=ENVELOPE_SCHEMA or row['role']!=role or row['source_id']!=entry['source_id']:
                return stop('SOURCE_MISMATCH',True)
            if row['classification']!='STORY_OFFLINE':
                return stop('UNATTESTED_RUNTIME_CLAIM',True)
            if row['identity']!=identity:
                return stop('IDENTITY_MISMATCH',True)
            if digest(row['content'])!=row['content_sha256']:
                return stop('DIGEST_MISMATCH',True)
            if meta is None:
                return stop('TRANSPORT_EVIDENCE_MISSING')
            if meta.get('classification')!='OFFLINE_TEST_METADATA':
                return stop('TRANSPORT_CLAIM_UNQUALIFIED',True)
            if meta.get('principal')!=entry['principal']:
                return stop('PRINCIPAL_MISMATCH',True)
            if meta.get('audience')!=entry['audience']:
                return stop('AUDIENCE_MISMATCH',True)
            if meta.get('scope')!=entry['scope']:
                return stop('SCOPE_MISMATCH',True)
            if meta.get('tenant_id')!=identity['tenant_id']:
                return stop('TRANSPORT_TENANT_MISMATCH',True)
            if meta.get('challenge')!=challenge:
                return stop('REPLAY',True)
            if meta.get('envelope_sha256')!=digest(row):
                return stop('ENVELOPE_BINDING_MISMATCH',True)
            observed,collected=_utc(row['observed_at']),_utc(meta['collected_at'])
            if not observed<=collected<=now:
                return stop('CLOCK_ORDER',True)
            if now-observed>timedelta(seconds=entry['max_age_seconds']):
                return stop('STALE_SOURCE')
            if type(row['version']) is not int or row['version']<0:
                return stop('VERSION_INVALID',True)
            if role in ('core','twin','policy'):
                if row['snapshot_id']!=expected['snapshot_id'] or row['parent_snapshot_id'] is not None:
                    return stop('SNAPSHOT_MISMATCH',True)
            else:
                if row['parent_snapshot_id']!=expected['snapshot_id']:
                    return stop('SNAPSHOT_MISMATCH',True)
            if role in stable:
                if digest(row)!=digest(stable[role]):
                    return stop('READBACK_CHANGED',True)
            else:
                stable[role]=row
                if role in ('core','history','postcheck','terminal'):
                    phases.append(observed)
        if not all(a<b for a,b in zip(phases,phases[1:])):
            return stop('CHRONOLOGY_INVALID',True)
        if (stable['terminal']['version']<=stable['core']['version']
                or not _id(stable['terminal']['snapshot_id'])
                or stable['terminal']['snapshot_id']==expected['snapshot_id']):
            return stop('TERMINAL_CONTINUITY_INVALID',True)
        return stop('OFFLINE_TRANSPORT_CONSISTENT_NOT_AUTHENTICATED')
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,RecursionError):
        return stop('INPUT_INVALID',True)
