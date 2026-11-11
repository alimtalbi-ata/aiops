import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';
import {settleEvidenceRequest} from './evidence_request_settlement.mjs';

// Synthetic FS1113-only fixtures. No HTTP, live evidence, or Portal controller.
test('synthetic FS1113: invalidate before queued success microtask suppresses publication', async () => {
  const gate = createEvidenceRequestGate();
  const events = [];
  const work = settleEvidenceRequest(gate, gate.issue(), Promise.resolve('SYNTHETIC_READY'), {
    onSuccess: value => events.push(value),
    onError: () => events.push('SYNTHETIC_ERROR')
  });
  gate.invalidate();
  await work;
  assert.deepEqual(events, []);
});

test('synthetic FS1113: dispose before queued rejection suppresses error publication', async () => {
  const gate = createEvidenceRequestGate();
  const events = [];
  const work = settleEvidenceRequest(gate, gate.issue(), Promise.reject(new Error('SYNTHETIC_405')), {
    onSuccess: value => events.push(value),
    onError: error => events.push(error.message)
  });
  gate.dispose();
  await work;
  assert.deepEqual(events, []);
});

test('synthetic FS1113: current presentation callback exception remains observable', async () => {
  const gate = createEvidenceRequestGate();
  const expected = new Error('SYNTHETIC_RENDER_FAILURE');
  const work = settleEvidenceRequest(gate, gate.issue(), Promise.resolve('SYNTHETIC_UNKNOWN'), {
    onSuccess: () => { throw expected; },
    onError: () => assert.fail('success callback exception must not be converted into an FS1113 error')
  });
  await assert.rejects(work, error => error === expected);
});
