import test from 'node:test';
import assert from 'node:assert/strict';
import { SAN_PAYMENTS_STEPS, describeSanPaymentsJourney, renderSanPaymentsJourney } from './san_payments_journey.mjs';

test('synthetic: eight stages are ordered, missing data is UNKNOWN and never approved', () => {
  const steps = describeSanPaymentsJourney();
  assert.equal(steps.length, 8);
  assert.deepEqual(steps.map(s => s.id), SAN_PAYMENTS_STEPS.map(s => s.id));
  assert.ok(steps.every(s => s.state === 'UNKNOWN' && s.isOperationalClaim === false));
});

test('synthetic: forged READY and missing decision cannot imply human approval', () => {
  const steps = describeSanPaymentsJourney({
    decision: { state: 'READY', detail: 'synthetic: approved' },
    result: { state: 'BLOCKED', detail: 'synthetic: blocked' }
  });
  assert.equal(steps[6].state, 'UNKNOWN');
  assert.equal(steps[7].state, 'BLOCKED');
  assert.equal(steps[6].isOperationalClaim, false);
});

test('synthetic: semantic ordered navigation, text-only untrusted content and provenance', () => {
  const nodes = [];
  const document = { createElement(tag) {
    const node = { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
    nodes.push(node); return node;
  }};
  const root = { children: [], append(node) { this.children.push(node); } };
  const nav = renderSanPaymentsJourney(document, root, {
    incident: { state: 'ERROR', detail: '<script>alert(1)</script>', source: 'SYNTHETIC' }
  });
  assert.equal(nav.tag, 'nav');
  assert.match(nav.attributes['aria-label'], /SAN vers Payments/);
  const list = nav.children[2];
  assert.equal(list.tag, 'ol');
  assert.equal(list.children.length, 8);
  assert.equal(list.children[0].children[1].textContent, '<script>alert(1)</script>');
  assert.match(list.children[0].children[2].textContent, /SYNTHETIC/);
  assert.equal(root.children[0], nav);
  assert.equal(nodes.filter(n => n.tag === 'script').length, 0);
});
