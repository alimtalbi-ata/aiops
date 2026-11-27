"""Bind a synthetic admission receipt to independent server-owned readback.

The reader must resolve authenticated Core and isolated Evidence via the
existing dynamic_context(include_signals=True) contract. This is not tenant
ACL qualification or authentication of Evidence's legacy HTTP endpoint.
"""
from copy import deepcopy
from collector_receipt import digest, validate_receipt
from evidence_retrieval import index_references


def verify_persisted_receipt(correlation, response, *, read_context):
    """Return the verified run ID or raise; no publication or retry."""
    def require(ok):
        if not ok:
            raise ValueError('persisted collector receipt mismatch')

    # Freeze the validated JSON inputs before invoking external readback.
    expected_correlation = deepcopy(correlation)
    expected_response = deepcopy(response)
    run_id = validate_receipt(expected_correlation, expected_response)
    correlation_hash = digest(expected_correlation)
    response_hash = digest(expected_response)
    incident = expected_correlation['incidents'][0]
    publication = expected_response['publication']
    expected_run = publication['core']['run']
    expected_refs = index_references(publication['stored_evidence'])
    core, context = read_context(run_id)
    # The caller may persist a digest of the original response after verification.
    require(digest(correlation) == correlation_hash and digest(response) == response_hash)
    require(core.get('classification') == 'SYNTHETIC_CANONICAL_RUN'
            and core.get('policy') == 'DENY' and core.get('production_authorized') is False
            and core['run'] == expected_run
            and context.get('classification') == 'SYNTHETIC_LAB_CONTEXT'
            and context.get('policy') == 'DENY' and context.get('production_authorized') is False
            and context.get('run_id') == run_id and context.get('root') == incident['resource'])
    rows = context['verified_signals']
    require(index_references(context['evidence']) == expected_refs
            and index_references(rows) == expected_refs)
    signals = {signal['event_id']: signal for signal in incident['evidence']}
    seen = set()
    for row in rows:
        signal = row['signal']
        event_id = signal['event_id']
        require(event_id not in seen and signals.get(event_id) == signal)
        seen.add(event_id)
        require(row['payload_hash'] == digest({'run_id': run_id, 'incident_id': expected_run['incident_id'],
                'signal': signal, 'correlation_id': incident['id'], 'resource': incident['resource']}))
    require(seen == set(signals))
    return run_id
