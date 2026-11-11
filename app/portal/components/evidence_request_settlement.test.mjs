import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';
import {settleEvidenceRequest} from './evidence_request_settlement.mjs';

// All fixtures are synthetic; no HTTP, tenant data, or Portal controller wiring.
function deferred() {
  let resolve, reject;
  const promise = new Promise((res, rej) => { resolve = res; reject = rej; });
  return {promise, resolve, reject};
}
test('synthetic FS1113: old success after new success cannot overwrite UI', async () => {
  const gate = createEvidenceRequestGate(), old = deferred(), latest = deferred(), shown = [];
  const callbacks = {onSuccess: v => shown.push(v), onError: () => shown.push('ERROR')};
  const a = settleEvidenceRequest(gate, gate.issue(), old.promise, callbacks);
  const b = settleEvidenceRequest(gate, gate.issue(), latest.promise, callbacks);
  latest.resolve('SYNTHETIC_CURRENT'); await b;
  old.resolve('SYNTHETIC_STALE'); await a;
  assert.deepEqual(shown, ['SYNTHETIC_CURRENT']);
});
test('synthetic FS1113: stale rejection cannot replace latest EMPTY', async () => {
  const gate = createEvidenceRequestGate(), old = deferred(), latest = deferred(), shown = [];
  const callbacks = {onSuccess: v => shown.push(v), onError: () => shown.push('ERROR')};
  const a = settleEvidenceRequest(gate, gate.issue(), old.promise, callbacks);
  const b = settleEvidenceRequest(gate, gate.issue(), latest.promise, callbacks);
  latest.resolve('EMPTY'); await b;
  old.reject(new Error('SYNTHETIC_404')); await a;
  assert.deepEqual(shown, ['EMPTY']);
});
test('synthetic FS1113: navigation and unmount suppress both outcomes', async () => {
  for (const kind of ['navigation', 'unmount']) {
    const gate = createEvidenceRequestGate(), pending = deferred(), shown = [];
    const task = settleEvidenceRequest(gate, gate.issue(), pending.promise, {
      onSuccess: v => shown.push(v), onError: () => shown.push('ERROR')
    });
    if (kind === 'navigation') gate.invalidate(); else gate.dispose();
    pending.reject(new Error('SYNTHETIC_405')); await task;
    assert.deepEqual(shown, []);
  }
});
test('synthetic FS1113: current errors are delivered, not hidden', async () => {
  const gate = createEvidenceRequestGate(), shown = [];
  await settleEvidenceRequest(gate, gate.issue(), Promise.reject(new Error('SYNTHETIC_404')), {
    onSuccess: () => shown.push('READY'), onError: e => shown.push(e.message)
  });
  assert.deepEqual(shown, ['SYNTHETIC_404']);
});
