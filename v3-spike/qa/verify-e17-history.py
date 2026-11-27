"""Offline consistency of E17 history projections; not raw Temporal attestation."""
import calendar
import copy
from datetime import datetime
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


def timestamp_ns(value, *, fractional=True):
    """Validate the calendar and preserve all nine fractional digits."""
    suffix = r'\.([0-9]{9})Z' if fractional else 'Z'
    match = re.fullmatch(r'([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})' + suffix, value) if isinstance(value, str) else None
    if match is None:
        raise ValueError('invalid timestamp format')
    instant = datetime.strptime(match[1], '%Y-%m-%dT%H:%M:%S')
    return calendar.timegm(instant.timetuple()) * 1_000_000_000 + (int(match[2]) if fractional else 0)


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
    times = [timestamp_ns(e['event_time']) for e in events]
    check('event timestamps', times == sorted(times))
    receipt_second = timestamp_ns(receipt['completed_at'], fractional=False)
    check('receipt second overlaps activity', receipt_second <= times[6] and times[5] < receipt_second + 1_000_000_000)
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
    def mutate_times(d, transform):
        for history in d[:2]:
            for event in history['events']:
                event['event_time'] = transform(event['event_time'])

    # Equal timestamps can be legitimate at the available clock resolution.
    positive = copy.deepcopy(docs)
    for history in positive[:2]:
        history['events'][1]['event_time'] = history['events'][0]['event_time']
    verify(positive)
    mutations = [
        ('invalid month', lambda d: mutate_times(d, lambda t: t[:5] + '99' + t[7:])),
        ('invalid day', lambda d: mutate_times(d, lambda t: t[:8] + '99' + t[10:])),
        ('invalid hour', lambda d: mutate_times(d, lambda t: t[:11] + '99' + t[13:])),
        ('receipt outside activity', lambda d: mutate_times(d, lambda t: '2025' + t[4:])),
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
    print(json.dumps({'result': 'PASS', 'checks': checks, 'negative': [name for name, _ in mutations], 'positive_mutations': ['equal adjacent event times'], 'archive_sha256': expected, 'production_authorized': False, 'limitations': 'Offline projected history consistency only; not raw history, authentication, causality or runtime.'}, sort_keys=True))


if __name__ == '__main__':
    main(*sys.argv[1:])
