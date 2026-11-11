import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';
import {settleEvidenceRequest} from './evidence_request_settlement.mjs';

// All fixtures are synthetic. No HTTP, operational data, or production controller.
test('synthetic FS1113: hostile thenable cannot publish twice', async () => {
  const gate = createEvidenceRequestGate();
  const published = [];
  const hostile = {then(resolve, reject) {
    resolve('SYNTHETIC_EMPTY');
    reject(new Error('SYNTHETIC_405'));
    resolve('SYNTHETIC_READY');
  }};
  await settleEvidenceRequest(gate, gate.issue(), hostile, {
    onSuccess: value => published.push(value),
    onError: () => published.push('ERROR')
  });
  assert.deepEqual(published, ['SYNTHETIC_EMPTY']);
});

test('synthetic FS1113: navigation invalidates resolved response before callback microtask', async () => {
  const gate = createEvidenceRequestGate();
  const published = [];
  const token = gate.issue();
  const pending = settleEvidenceRequest(gate, token, Promise.resolve('SYNTHETIC_READY'), {
    onSuccess: value => published.push(value),
    onError: () => published.push('ERROR')
  });
  gate.invalidate();
  await pending;
  assert.deepEqual(published, []);
});

test('synthetic FS1113: unmount prevents late 404 error callback', async () => {
  const gate = createEvidenceRequestGate();
  const published = [];
  const token = gate.issue();
  const pending = settleEvidenceRequest(gate, token, Promise.reject(new Error('SYNTHETIC_404')), {
    onSuccess: value => published.push(value),
    onError: error => published.push(error.message)
  });
  gate.dispose();
  await pending;
  assert.deepEqual(published, []);
});
