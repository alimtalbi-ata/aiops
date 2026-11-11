import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';
import {settleEvidenceRequest} from './evidence_request_settlement.mjs';

// All values and events are synthetic FS1113 fixtures; no HTTP or operational data.
test('synthetic FS1113: current error callback failure remains observable', async () => {
  const gate = createEvidenceRequestGate();
  const expected = new Error('SYNTHETIC_RENDER_ERROR');
  const pending = settleEvidenceRequest(gate, gate.issue(), Promise.reject(new Error('SYNTHETIC_405')), {
    onSuccess: () => assert.fail('unexpected success'),
    onError: () => { throw expected; }
  });
  await assert.rejects(pending, error => error === expected);
});

test('synthetic FS1113: stale 404 rejection is consumed, current UNKNOWN remains visible', async () => {
  const gate = createEvidenceRequestGate();
  const events = [];
  let rejectOld;
  const old = new Promise((_, reject) => { rejectOld = reject; });
  const oldWork = settleEvidenceRequest(gate, gate.issue(), old, {
    onSuccess: () => events.push('STALE_SUCCESS'),
    onError: () => events.push('STALE_404')
  });
  const newWork = settleEvidenceRequest(gate, gate.issue(), Promise.resolve('SYNTHETIC_UNKNOWN'), {
    onSuccess: value => events.push(value),
    onError: () => events.push('NEW_ERROR')
  });
  await newWork;
  rejectOld(new Error('SYNTHETIC_404'));
  await oldWork;
  assert.deepEqual(events, ['SYNTHETIC_UNKNOWN']);
});

test('synthetic FS1113: invalid callbacks reject before assimilating a hostile thenable', async () => {
  const gate = createEvidenceRequestGate();
  let touched = false;
  const hostile = {get then() { touched = true; throw new Error('SYNTHETIC_THENABLE'); }};
  await assert.rejects(settleEvidenceRequest(gate, gate.issue(), hostile, {
    onSuccess: null,
    onError: () => {}
  }), TypeError);
  assert.equal(touched, false);
});
