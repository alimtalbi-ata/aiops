import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';
import {settleEvidenceRequest} from './evidence_request_settlement.mjs';

// Synthetic FS1113 fixtures only. No HTTP, production evidence or runtime controller.
test('synthetic FS1113: new request supersedes a queued older success', async () => {
  const gate = createEvidenceRequestGate();
  const published = [];
  let resolveOld;
  const old = new Promise(resolve => { resolveOld = resolve; });
  const first = settleEvidenceRequest(gate, gate.issue(), old, {
    onSuccess: value => published.push(value),
    onError: () => published.push('SYNTHETIC_ERROR')
  });
  const second = settleEvidenceRequest(gate, gate.issue(), Promise.resolve('SYNTHETIC_UNKNOWN'), {
    onSuccess: value => published.push(value),
    onError: () => published.push('SYNTHETIC_ERROR')
  });
  resolveOld('SYNTHETIC_READY');
  await Promise.all([first, second]);
  assert.deepEqual(published, ['SYNTHETIC_UNKNOWN']);
});

test('synthetic FS1113: throwing then getter reports only current error', async () => {
  const gate = createEvidenceRequestGate();
  const published = [];
  const broken = Object.create(null, {
    then: {get() { throw new Error('SYNTHETIC_THENABLE_ERROR'); }}
  });
  await settleEvidenceRequest(gate, gate.issue(), broken, {
    onSuccess: () => published.push('SYNTHETIC_READY'),
    onError: error => published.push(error.message)
  });
  assert.deepEqual(published, ['SYNTHETIC_THENABLE_ERROR']);
});

test('synthetic FS1113: superseded throwing then getter cannot replace latest EMPTY', async () => {
  const gate = createEvidenceRequestGate();
  const published = [];
  const broken = Object.create(null, {
    then: {get() { throw new Error('SYNTHETIC_405'); }}
  });
  const stale = settleEvidenceRequest(gate, gate.issue(), broken, {
    onSuccess: () => published.push('SYNTHETIC_READY'),
    onError: error => published.push(error.message)
  });
  const current = settleEvidenceRequest(gate, gate.issue(), Promise.resolve('SYNTHETIC_EMPTY'), {
    onSuccess: value => published.push(value),
    onError: () => published.push('SYNTHETIC_ERROR')
  });
  await Promise.all([stale, current]);
  assert.deepEqual(published, ['SYNTHETIC_EMPTY']);
});
