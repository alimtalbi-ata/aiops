"""Pure B/C continuity contract. No authority is established by fixtures."""
from copy import deepcopy
from datetime import timedelta
from .acme_runtime_context import qualify_context, digest, _utc, IDENTITY, RECEIPT
from worker.acme_simulated_hitl import verify_no_effect_receipt


def qualify_continuity(expected, intent, readbacks, policies, *, as_of_utc,
                       source_registry, prepared, terminal, receipt,
                       c_manifest, independently_read, expected_sha,
                       validate_postcheck, validate_manifest, continuity_sources,
                       history, postcheck, terminal_readback):
    """C predicates are injected as real functions, never as verdict documents."""
    base = qualify_context(expected, intent, readbacks, policies,
                           as_of_utc=as_of_utc, source_registry=source_registry)
    if base['reason'] != 'INJECTED_READBACKS_NOT_ATTESTED':
        return base
    def refuse(reason, reject=True):
        return dict(base, qualification='REJECT' if reject else 'BLOCK',
                    reason=reason, context=None, evidence=[])
    if any(x is None for x in (prepared, terminal, receipt, c_manifest, independently_read)):
        return refuse('CONTINUITY_EVIDENCE_MISSING', False)
    if any(x is None for x in (history, postcheck, terminal_readback)):
        return refuse('CONTINUITY_EVIDENCE_MISSING', False)
    try:
        roles = ('history', 'postcheck', 'terminal')
        if type(continuity_sources) is not dict or set(continuity_sources) != set(roles):
            return refuse('CONTINUITY_SOURCE_MISSING', False)
        from .acme_runtime_context import _id
        if not all(_id(v) for v in continuity_sources.values()):
            return refuse('CONTINUITY_SOURCE_INVALID')
        if any(type(policies.get(v)) is not int or policies[v] < 0
               for v in continuity_sources.values()):
            return refuse('FRESHNESS_POLICY_MISSING', False)
        # Work with immutable-by-value snapshots; never mutate caller documents.
        prepared, terminal, receipt, c_manifest, independently_read = deepcopy(
            (prepared, terminal, receipt, c_manifest, independently_read))
        now = _utc(as_of_utc)
        identity = {k: expected[k] for k in IDENTITY}
        seven = {k: intent[k] for k in RECEIPT}
        fields = {'identity','snapshot_id','parent_snapshot_id','version','phase',
                  'observed_at','payload','manifest_sha256','collected_at'}
        for row in (prepared, terminal):
            if type(row) is not dict or set(row) != fields:
                return refuse('MANIFEST_SHAPE')
            if row['identity'] != identity:
                return refuse('IDENTITY_MISMATCH')
            body = {k:v for k,v in row.items() if k not in ('manifest_sha256','collected_at')}
            if digest(body) != row['manifest_sha256']:
                return refuse('MANIFEST_DIGEST_MISMATCH')
            observed, collected = _utc(row['observed_at']), _utc(row['collected_at'])
            if not observed <= collected <= now:
                return refuse('OBSERVATION_COLLECTION_ORDER')
            age = now - observed
            if age > timedelta(seconds=policies[source_registry['core'] if row is prepared else continuity_sources['terminal']]):
                return refuse('STALE_MANIFEST', False)
            if type(row['version']) is not int or row['version'] < 0:
                return refuse('VERSION_INVALID')
        core = readbacks['core']['content']
        if (prepared['phase'] != 'PREPARED' or prepared['parent_snapshot_id'] is not None
                or prepared['snapshot_id'] != expected['snapshot_id']
                or prepared['version'] != core.get('version')
                or core.get('run_status') != 'PREPARED' or core.get('incident_status') != 'PREPARED'
                or prepared['observed_at'] != readbacks['core']['observed_at']):
            return refuse('PREPARED_MISMATCH')
        manifest = {a:digest(readbacks[a]) for a in ('twin','policy')}
        if core.get('authority_manifest') != manifest or prepared['payload'] != {
                'core_sha256':digest(readbacks['core']), 'authority_manifest':manifest}:
            return refuse('AUTHORITY_MANIFEST_MISMATCH')
        if (terminal['phase'] != 'TERMINAL' or terminal['parent_snapshot_id'] != prepared['snapshot_id']
                or terminal['snapshot_id'] == prepared['snapshot_id']
                or not isinstance(terminal['snapshot_id'],str) or not terminal['snapshot_id']
                or terminal['version'] <= prepared['version']
                or _utc(terminal['observed_at']) <= _utc(prepared['observed_at'])):
            return refuse('TERMINAL_CONTINUITY_MISMATCH')
        if not verify_no_effect_receipt(receipt, seven) or type(receipt['effect_receipts']) is not int:
            return refuse('RECEIPT_INVALID')
        import hashlib
        nonce = readbacks['twin']['content'].get('approval_nonce')
        if (type(nonce) is not str or not nonce or not nonce.isascii()
                or receipt['twin_approval_nonce_sha256'] != hashlib.sha256(nonce.encode('ascii')).hexdigest()
                or receipt['core_request_sha256'] != core.get('request_sha256')
                or receipt['core_source_event_ids'] != core.get('source_event_ids')):
            return refuse('RECEIPT_PREPARED_MISMATCH')
        actual = independently_read.get('terminal')
        if (not isinstance(actual,dict) or actual.get('version') != terminal['version']
                or actual.get('observed_at') != terminal['observed_at']
                or actual.get('snapshot_id') != terminal['snapshot_id']
                or actual.get('parent_snapshot_id') != prepared['snapshot_id']
                or actual.get('impact_incident_id') != expected['impact_incident_id']
                or terminal['payload'] != {'terminal_readback_sha256':digest(actual),
                    'prepared_manifest_sha256':prepared['manifest_sha256'],
                    'receipt_sha256':receipt['receipt_sha256']}
                or c_manifest.get('worker_receipt') != receipt):
            return refuse('TERMINAL_READBACK_MISMATCH')
        if terminal_readback != actual:
            return refuse('TERMINAL_READBACK_CHANGED')
        for role, row in zip(roles, (history, postcheck, actual)):
            if (type(row) is not dict or row.get('identity') != seven
                    or row.get('parent_snapshot_id') != prepared['snapshot_id']
                    or row.get('impact_incident_id') != expected['impact_incident_id']
                    or row.get('source_id') != continuity_sources[role]):
                return refuse('CONTINUITY_SOURCE_BINDING')
            observed = _utc(row.get('observed_at'))
            if observed > now:
                return refuse('FUTURE_OBSERVATION')
            if now - observed > timedelta(seconds=policies[continuity_sources[role]]):
                return refuse('STALE_CONTINUITY_SOURCE', False)
        times = [_utc(x['observed_at']) for x in (prepared, history, postcheck, actual)]
        if not all(a < b for a,b in zip(times,times[1:])):
            return refuse('CONTINUITY_TIME_ORDER')
        if (history.get('receipt_sha256') != receipt['receipt_sha256']
                or postcheck.get('history_sha256') != digest(history)
                or postcheck.get('verified') is not True
                or actual.get('postcheck_sha256') != digest(postcheck)
                or independently_read.get('history_sha256') != digest(history)):
            return refuse('CONTINUITY_DIGEST_MISMATCH')
        post = validate_postcheck(intent=intent, independently_read=independently_read)
        final = validate_manifest(c_manifest, expected_sha=expected_sha, intent=intent,
                                  independently_read=independently_read)
        if (post != {'qualification':'CONTRACT_ONLY','runtime_attested':False,'finish_authorized':False}
                or final != {'qualification':'CONTRACT_ONLY','runtime_attested':False,'resolution_authorized':False}):
            return refuse('C_VALIDATOR_UNQUALIFIED')
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
        return refuse('CONTINUITY_INVALID')
    return dict(base, reason='OFFLINE_CONTINUITY_CONSISTENT_NOT_ATTESTED')
