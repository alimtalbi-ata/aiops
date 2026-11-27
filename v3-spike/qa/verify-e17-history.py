"""Offline consistency of E17 history projections; not raw Temporal attestation."""
import copy
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

TYPES = (
    'WORKFLOW_EXECUTION_STARTED', 'WORKFLOW_TASK_SCHEDULED',
    'WORKFLOW_TASK_STARTED', 'WORKFLOW_TASK_COMPLETED',
    'ACTIVITY_TASK_SCHEDULED', 'ACTIVITY_TASK_STARTED',
    'ACTIVITY_TASK_COMPLETED', 'WORKFLOW_TASK_SCHEDULED',
    'WORKFLOW_TASK_STARTED', 'WORKFLOW_TASK_COMPLETED',
    'WORKFLOW_EXECUTION_COMPLETED',
)
FILES = ('e17-history-before.json', 'e17-history-after.json',
         'temporal-e17-product.json', 'temporal-e17-product-worker.json',
         'temporal-e17-product-worker-replay.json', 'temporal-e17-recreated-target.json',
         'e17-browser/e17-browser.json')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def verify(docs):
    h, after, report, worker, replay, recreated, browser = docs
    checks = []
    def check(name, condition):
        if not condition:
            raise ValueError(name)
        checks.append(name)
    receipt = report['action_receipt']
    binding = receipt['binding']
    verification = report['verification']
    events = h['events']
    check('history classification', h['classification'] == 'V3_E17_TEMPORAL_HISTORY_PROJECTION')
    check('restart consistency', canonical(h) == canonical(after))
    check('event IDs', [e['event_id'] for e in events] == list(range(1, 12)))
    check('event types', tuple(e['event_type'] for e in events) == TYPES)
    times = [e['event_time'] for e in events]
    check('event timestamps', all(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{9}Z', t) for t in times) and times == sorted(times))
    check('activity links', [h[k] for k in ('scheduled_event_id', 'started_event_id', 'completed_event_id')] == [5, 6, 7])
    check('activity attempt', type(h['activity_attempt']) is int and h['activity_attempt'] == 1 and bool(h['activity_identity']))
    check('workflow and activity type', h['workflow_type'] == 'E17ProductRecoveryWorkflow' and h['activity_type'] == 'v3_e17_reset_lab_http_delay')
    check('result bindings', all(canonical(r) == canonical(receipt) for r in (h['activity_result'], h['workflow_result'], worker['action_receipt'])))
    check('worker replay', canonical(worker) == canonical(replay))
    digest = hashlib.sha256(canonical(receipt)).hexdigest()
    check('receipt digest', all(x == digest for x in (h['action_receipt_sha256'], report['action_receipt_sha256'], worker['action_receipt_sha256'], verification['action_receipt_sha256'], browser['receipt_sha256'], recreated['historical_receipt_sha256'])))
    rid = h['workflow_id']
    check('run binding', bool(re.fullmatch(r'RUN-[A-F0-9]{16}', rid)) and all(x == rid for x in (report['workflow_id'], worker['run_id'], binding['run_id'], binding['workflow_id'], verification['original_run_id'], browser['original_run_id'], recreated['run_id'])) and verification['comparison_run_id'] != rid and browser['comparison_run_id'] == verification['comparison_run_id'])
    check('approval binding', h['approval'] == {k: binding[k] for k in ('receipt_id', 'receipt_sha256')})
    check('action binding', receipt['receipt_id'] == verification['action_receipt_id'] and binding['lab_action']['action'] == 'RESET_LAB_HTTP_DELAY' and binding['lab_action']['target_id'] == report['target_audit']['target_id'])
    check('activity counts', report['history_events'] == worker['history_events'] == len(events) and report['activities_completed'] == worker['activities_completed'] == 1)
    check('target recreation', recreated['new_target_id'] != binding['lab_action']['target_id'] and recreated['old_approval_rejected'] is True and recreated['reservation_replay_blocked'] is True and canonical(recreated['audit']) == canonical(report['target_audit']))
    check('safety', all(d['production_authorized'] is False for d in [*docs, receipt, verification]) and all(d['operational_decision'] == 'DENY' for d in (receipt, worker, verification)) and receipt['executed_on_host'] is False and receipt['status'] == 'SIMULATED')
    check('limitations retained', h['raw_history_exported'] is False and report['core_business_stages_qualified'] is False and verification['causality_established'] is False)
    return checks


def main(path, expected):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
        raise ValueError('archive digest mismatch')
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None or len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError('invalid ZIP')
        docs = [json.loads(archive.read(name)) for name in FILES]
    checks = verify(docs)
    mutations = [
        ('restart', lambda d: d[1].update(activity_attempt=2)),
        ('event ID', lambda d: [x['events'][4].update(event_id=4) for x in d[:2]]),
        ('event order', lambda d: [x['events'][6].update(event_time=x['events'][0]['event_time']) for x in d[:2]]),
        ('activity links', lambda d: [x.update(completed_event_id=8) for x in d[:2]]),
        ('approval', lambda d: [x['approval'].update(receipt_id='OTHER') for x in d[:2]]),
        ('receipt', lambda d: d[2].update(action_receipt_sha256='0'*64)),
        ('replay', lambda d: d[4].update(history_events=10)),
        ('target', lambda d: d[5].update(old_approval_rejected=False)),
        ('production', lambda d: d[6].update(production_authorized=True)),
    ]
    for name, mutate in mutations:
        candidate = copy.deepcopy(docs)
        mutate(candidate)
        try:
            verify(candidate)
        except ValueError:
            continue
        raise AssertionError('accepted mutation: ' + name)
    print(json.dumps({'result': 'PASS', 'checks': checks, 'negative': [name for name, _ in mutations], 'archive_sha256': expected, 'production_authorized': False, 'limitations': 'Offline projected history consistency only; not raw history, authentication, causality or runtime.'}, sort_keys=True))


if __name__ == '__main__':
    main(*sys.argv[1:])
