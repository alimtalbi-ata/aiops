"""Bind disposable rootless PostgreSQL restore to actual E17 LAB receipts."""
import hashlib
import json
import os
import re
import sys
import subprocess
from poc_restore_smoke import CI_ROOT, Lifecycle, prove, require, snapshot

RUN = r'RUN-[A-F0-9]{16}'
HEX = r'[a-f0-9]{64}'
EVIDENCE = r'[A-Za-z0-9_.-]{1,128}'


def matches(pattern, value):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def binding(report, worker, gamma, boundary):
    for receipt in (report, gamma, boundary):
        require(receipt['result'] == 'PASS' and receipt['production_authorized'] is False,
                'unqualified LAB receipt')
    require(report['classification'] == 'V3_TEMPORAL_E17_LAB_RUNTIME'
            and worker['classification'] == 'V3_E17_WORKER_RECEIPT_READBACK'
            and gamma['classification'] == 'V3_GAMMA_E17_REAL_READBACK'
            and boundary['classification'] == 'V3_TEMPORAL_BOUNDARY_RUNTIME',
            'wrong receipt classification')
    verify = report['verification']
    original, comparison, boundary_run = (report['workflow_id'], verify['comparison_run_id'],
                                           boundary['run_id'])
    runs = [original, comparison, boundary_run]
    require(all(matches(RUN, item) for item in runs) and len(set(runs)) == 3,
            'invalid distinct run identities')
    digest = report['action_receipt_sha256']
    actual = hashlib.sha256(json.dumps(report['action_receipt'], sort_keys=True,
                                      separators=(',', ':'), allow_nan=False).encode()).hexdigest()
    require(matches(HEX, digest) and digest == actual
            and worker['run_id'] == original and worker['action_receipt'] == report['action_receipt']
            and worker['production_authorized'] is False and worker['operational_decision'] == 'DENY'
            and worker['action_receipt_sha256'] == gamma['action_receipt_sha256'] == digest
            and gamma['original_run_id'] == verify['original_run_id'] == original
            and gamma['comparison_run_id'] == comparison
            and verify['action_receipt_sha256'] == digest
            and verify['production_authorized'] is False and verify['operational_decision'] == 'DENY'
            and verify['status'] == gamma['verification'] == 'RECOVERED'
            and boundary['workflow_id'] == boundary_run and boundary['core_status'] == 'BLOCKED',
            'unbound E17 or boundary receipt')
    refs = {}
    for key in ('original_evidence', 'comparison_evidence'):
        group = verify[key]
        require(isinstance(group, list) and 1 <= len(group) <= 20, 'missing evidence')
        for item in group:
            eid, sha = item['evidence_id'], item['payload_hash']
            require(matches(EVIDENCE, eid) and matches(HEX, sha) and eid not in refs,
                    'invalid or duplicate evidence')
            refs[eid] = sha
    return {'runs': sorted(runs), 'boundary_run': boundary_run,
            'evidence': refs, 'action_receipt_sha256': digest}


def bound_snapshot(query, expected, *, project=snapshot):
    runs, refs, boundary = expected['runs'], expected['evidence'], expected['boundary_run']
    require(len(runs) == 3 and len(set(runs)) == 3 and all(matches(RUN, r) for r in runs)
            and boundary in runs and 2 <= len(refs) <= 40
            and all(matches(EVIDENCE, e) and matches(HEX, h) for e, h in refs.items()),
            'invalid SQL binding')

    def quoted(values):
        return ','.join("'" + value + "'" for value in sorted(values))

    actual_runs = json.loads(query(
        "SELECT coalesce(json_object_agg(run_id,mode),'{}')::text FROM aiops.runs WHERE run_id IN ("
        + quoted(runs) + ");"))
    require(actual_runs == {run: 'DEMO' for run in runs}, 'missing or non-DEMO run')
    actual_refs = json.loads(query(
        "SELECT coalesce(json_object_agg(evidence_id,payload_hash),'{}')::text FROM aiops.evidence "
        "WHERE evidence_id IN (" + quoted(refs) + ");"))
    require(actual_refs == refs, 'E17 evidence identity or digest mismatch')
    count = int(query("SELECT count(*) FROM aiops.execution_receipts WHERE run_id='"
                      + boundary + "' AND workflow_id='" + boundary + "';"))
    require(count == 1, 'missing exact Core execution receipt')
    return {**project(query), 'e17_binding': {'runs': runs, 'evidence_count': len(refs),
                                             'boundary_execution_receipt': True}}


def main():
    try:
        require(os.environ.get('GITHUB_ACTIONS') == 'true'
                and os.environ.get('RUNNER_ENVIRONMENT') == 'github-hosted'
                and os.environ.get('V3_ROOT') == str(CI_ROOT)
                and os.getuid() != 0 and matches(r'[a-f0-9]{40}', os.environ.get('GITHUB_SHA')),
                'disposable rootless CI only')
        ctl = Lifecycle(CI_ROOT)
        running = ctl.compose(['ps', '-q', '--status', 'running', 'worker'],
                              all_profiles=True, capture_output=True, text=True, timeout=20).stdout.strip()
        require(not running, 'orchestration writer still running')

        def read(name):
            raw = (CI_ROOT / name).read_bytes()
            require(0 < len(raw) <= 1024**2, 'invalid receipt size')
            return json.loads(raw)

        expected = binding(read('temporal-e17-product.json'),
                           read('temporal-e17-product-worker-replay.json'),
                           read('temporal-e17-product-gamma.json'),
                           read('temporal-boundary-replay.json'))
        receipt = prove(ctl, project_snapshot=lambda q: bound_snapshot(q, expected))
        receipt.update(classification='POC_ROOTLESS_POST_E17_PG_RESTORE_PROOF',
                       action_receipt_sha256=expected['action_receipt_sha256'],
                       core_business_stages_qualified=False, temporal_restore='NOT_RUN')
        print(json.dumps(receipt, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print('Post-E17 restore qualification failed: ' + type(exc).__name__, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
