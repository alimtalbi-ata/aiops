import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';
import {settleEvidenceRequest} from './evidence_request_settlement.mjs';

// Explicitly synthetic FS1113 events; no network or operational data.
test('success callback navigation suppresses older pending HTTP 405', async () => {
  const gate = createEvidenceRequestGate();
  const events = [];
  let rejectOld;
  const oldPending = new Promise((_, reject) => { rejectOld = reject; });
  const old = settleEvidenceRequest(gate, gate.issue(), oldPending, {
    onSuccess: () => events.push('old-success'), onError: () => events.push('old-error')
  });
  const current = settleEvidenceRequest(gate, gate.issue(), Promise.resolve('SYNTHETIC_READY'), {
    onSuccess: () => { events.push('current-success'); gate.invalidate(); },
    onError: () => events.push('current-error')
  });
  await current;
  rejectOld(Object.assign(new Error('synthetic HTTP 405'), {status: 405}));
  await old;
  assert.deepEqual(events, ['current-success']);
});

test('error callback unmount blocks later publication', async () => {
  const gate = createEvidenceRequestGate();
  const events = [];
  const token = gate.issue();
  await settleEvidenceRequest(gate, token, Promise.reject(new Error('synthetic 404')), {
    onSuccess: () => events.push('success'),
    onError: () => { events.push('error'); gate.dispose(); }
  });
  assert.equal(gate.issue(), null);
  await settleEvidenceRequest(gate, token, Promise.resolve('SYNTHETIC_READY'), {
    onSuccess: () => events.push('late-success'), onError: () => events.push('late-error')
  });
  assert.deepEqual(events, ['error']);
});

test('callback-issued generation suppresses stale replay', async () => {
  const gate = createEvidenceRequestGate();
  const events = [];
  const first = gate.issue();
  await settleEvidenceRequest(gate, first, Promise.resolve('SYNTHETIC_EMPTY'), {
    onSuccess: () => { events.push('empty'); gate.issue(); },
    onError: () => events.push('error')
  });
  await settleEvidenceRequest(gate, first, Promise.resolve('SYNTHETIC_STALE'), {
    onSuccess: () => events.push('stale'), onError: () => events.push('stale-error')
  });
  assert.deepEqual(events, ['empty']);
});
