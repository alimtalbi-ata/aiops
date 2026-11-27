"""Validate the existing synthetic admission receipt against local correlation.

This binds response content, not the identity of the HTTP server or collector.
"""
import hashlib
import json
import re


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_receipt(correlation, response):
    """Return the bound DEMO run ID or raise; no network or publication."""
    def require(ok):
        if not ok:
            raise ValueError('unbound collector receipt')

    require(correlation['classification'] == 'EXPERIMENTAL_SYNTHETIC' and len(correlation['incidents']) == 1)
    incident = correlation['incidents'][0]
    signals = incident['evidence']
    require(incident['tenant'] == 'synthetic-demo' and incident['policy'] == 'DENY'
            and incident['production_authorized'] is False and len(signals) == 3
            and len({s['event_id'] for s in signals}) == 3)
    batch_hash = digest(incident)
    incident_id = 'INC-CI-INGEST-' + batch_hash[:32]
    admission = response['admission']
    publication = response['publication']
    core = publication['core']
    run = core['run']
    run_id = run['run_id']
    require(response['production_authorized'] is False and publication['production_authorized'] is False
            and admission['production_authorized'] is False and admission['admitted'] is True
            and admission['classification'] == 'SYNTHETIC_MEASURED_INCIDENT_ADMISSION_V1'
            and admission['operational_decision'] == 'DENY' and admission['batch_sha256'] == batch_hash
            and admission['resource'] == incident['resource']
            and admission['references'] == [{'event_id': s['event_id'], 'sha256': s['sha256']} for s in signals]
            and publication['correlation'] == correlation)
    require(core['classification'] == 'SYNTHETIC_CANONICAL_RUN' and core['production_authorized'] is False
            and core['policy'] == 'DENY' and run['incident_id'] == incident_id
            and run['mode'] == 'DEMO' and run['status'] == 'CREATED'
            and isinstance(run_id, str) and re.fullmatch(r'RUN-[A-F0-9]{16}', run_id))
    expected = {digest({'run_id': run_id, 'incident_id': incident_id, 'signal': s,
                        'correlation_id': incident['id'], 'resource': incident['resource']}) for s in signals}
    receipts = publication['stored_evidence']
    require(isinstance(receipts, list) and len(receipts) == len(expected) == 3
            and all(isinstance(r['evidence_id'], str) and bool(r['evidence_id']) for r in receipts)
            and len({r['evidence_id'] for r in receipts}) == 3
            and {r['payload_hash'] for r in receipts} == expected)
    return run_id
