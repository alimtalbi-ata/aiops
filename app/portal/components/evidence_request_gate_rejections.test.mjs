import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';

// Synthetic responses only. No HTTP, tenant data, or runtime controller wiring.
function deferred() {
  let resolve, reject;
  const promise = new Promise((ok, fail) => { resolve = ok; reject = fail; });
  return {promise, resolve, reject};
}

test('synthetic FS1113 stale rejection cannot replace a newer successful view', async () => {
  const gate = createEvidenceRequestGate();
  const old = deferred(), fresh = deferred(), displayed = [];
  const oldToken = gate.issue();
  const oldTask = old.promise.then(
    value => { if (gate.isCurrent(oldToken)) displayed.push(value); },
    () => { if (gate.isCurrent(oldToken)) displayed.push('ERROR'); }
  );
  const freshToken = gate.issue();
  const freshTask = fresh.promise.then(
    value => { if (gate.isCurrent(freshToken)) displayed.push(value); },
    () => { if (gate.isCurrent(freshToken)) displayed.push('ERROR'); }
  );
  fresh.resolve('SYNTHETIC_CURRENT');
  await freshTask;
  old.reject(new Error('SYNTHETIC_STALE_FAILURE'));
  await oldTask;
  assert.deepEqual(displayed, ['SYNTHETIC_CURRENT']);
});

test('synthetic 404/405 are not converted into evidence by the request gate', async () => {
  for (const status of [404, 405]) {
    const gate = createEvidenceRequestGate();
    const token = gate.issue();
    const displayed = [];
    const response = {status, ok: false, body: 'SYNTHETIC_NO_EVIDENCE'};
    if (gate.isCurrent(token)) {
      displayed.push(response.ok ? response.body : 'ERROR');
    }
    assert.deepEqual(displayed, ['ERROR']);
    assert.equal(gate.isCurrent(token), true);
  }
});

test('synthetic navigation invalidation suppresses both completion and rejection', async () => {
  for (const reject of [false, true]) {
    const gate = createEvidenceRequestGate();
    const pending = deferred();
    const token = gate.issue();
    const displayed = [];
    const task = pending.promise.then(
      value => { if (gate.isCurrent(token)) displayed.push(value); },
      () => { if (gate.isCurrent(token)) displayed.push('ERROR'); }
    );
    gate.invalidate();
    if (reject) pending.reject(new Error('SYNTHETIC_NAV_FAILURE'));
    else pending.resolve('SYNTHETIC_NAV_STALE');
    await task;
    assert.deepEqual(displayed, []);
  }
});
