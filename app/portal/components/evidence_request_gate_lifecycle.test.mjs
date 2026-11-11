import test from 'node:test';
import assert from 'node:assert/strict';
import {createEvidenceRequestGate} from './evidence_request_gate.mjs';

// Synthetic UI lifecycle only: no HTTP, operational records, or controller wiring.
test('synthetic FS1113: disposed view rejects pending success and failure', async () => {
  for (const outcome of ['resolve', 'reject']) {
    const gate = createEvidenceRequestGate();
    const token = gate.issue();
    const displayed = [];
    let settle;
    const pending = new Promise((resolve, reject) => {
      settle = outcome === 'resolve' ? resolve : reject;
    });
    const task = pending.then(
      value => { if (gate.isCurrent(token)) displayed.push(value); },
      () => { if (gate.isCurrent(token)) displayed.push('ERROR'); }
    );
    gate.dispose();
    settle(outcome === 'resolve' ? 'SYNTHETIC_STALE' : new Error('SYNTHETIC_STALE'));
    await task;
    assert.deepEqual(displayed, []);
    assert.equal(gate.issue(), null);
    assert.equal(gate.isCurrent(token), false);
  }
});

test('synthetic FS1113: invalid tokens never publish and invalidation is monotonic', () => {
  const gate = createEvidenceRequestGate();
  const first = gate.issue();
  for (const token of [null, undefined, 0, -1, 1.5, NaN, Infinity, '1', {}, Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(gate.isCurrent(token), false);
  }
  gate.invalidate();
  assert.equal(gate.isCurrent(first), false);
  const second = gate.issue();
  assert.equal(gate.isCurrent(second), true);
  assert.equal(gate.isCurrent(first), false);
  gate.dispose();
  gate.invalidate();
  assert.equal(gate.isCurrent(second), false);
  assert.equal(gate.issue(), null);
});
