import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';
import {settleEvidenceRequest} from './evidence_request_settlement.mjs';

// Synthetic UI-only thenables; no network, production evidence, or controller wiring.
test('synthetic FS1113: stale thenable rejection after newer UNKNOWN is ignored', async () => {
  const gate = createEvidenceRequestGate(), shown = [];
  let rejectOld;
  const old = {then(resolve, reject) { rejectOld = reject; }};
  const callbacks = {onSuccess: value => shown.push(value), onError: () => shown.push('ERROR')};
  const first = settleEvidenceRequest(gate, gate.issue(), old, callbacks);
  await Promise.resolve(); // Let Promise.resolve assimilate the synthetic thenable.
  const second = settleEvidenceRequest(gate, gate.issue(), Promise.resolve('UNKNOWN'), callbacks);
  await second;
  rejectOld(new Error('SYNTHETIC_STALE_405'));
  await first;
  assert.deepEqual(shown, ['UNKNOWN']);
});

test('synthetic FS1113: malformed thenable rejection is delivered only when current', async () => {
  const gate = createEvidenceRequestGate(), shown = [];
  const broken = {then() { throw new Error('SYNTHETIC_THENABLE_FAILURE'); }};
  await settleEvidenceRequest(gate, gate.issue(), broken, {
    onSuccess: () => shown.push('READY'),
    onError: error => shown.push(error.message)
  });
  assert.deepEqual(shown, ['SYNTHETIC_THENABLE_FAILURE']);
});

test('synthetic FS1113: callbacks throwing remain observable to caller', async () => {
  const gate = createEvidenceRequestGate();
  await assert.rejects(
    settleEvidenceRequest(gate, gate.issue(), Promise.resolve('SYNTHETIC_READY'), {
      onSuccess: () => { throw new Error('SYNTHETIC_RENDER_FAILURE'); },
      onError: () => { throw new Error('UNEXPECTED_ERROR_CALLBACK'); }
    }),
    /SYNTHETIC_RENDER_FAILURE/
  );
});
