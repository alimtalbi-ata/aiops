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
  assert.equal(list.children[0].children[2].textContent, '<script>alert(1)</script>');
  assert.match(list.children[0].children[4].textContent, /SYNTHETIC/);
  assert.equal(root.children[0], nav);
  assert.equal(nodes.filter(n => n.tag === 'script').length, 0);
});

test('synthetic: all states expose actionable guidance without claiming freshness', () => {
  const states = ['LOADING', 'EMPTY', 'ERROR', 'UNKNOWN', 'BLOCKED', 'AVAILABLE'];
  for (const state of states) {
    const step = describeSanPaymentsJourney({ incident: { state, observedAt: 'SYNTHETIC-2026-01-01' } })[0];
    assert.equal(step.state, state);
    assert.ok(step.guidance.length > 15);
    assert.equal(step.isOperationalClaim, false);
  }
});

test('synthetic: provenance and guidance are text, not inferred evidence', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k,v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { append() {} };
  const nav = renderSanPaymentsJourney(document, root, {
    decision: { state: 'BLOCKED', source: 'SYNTHETIC', observedAt: 'not verified' }
  });
  const decision = nav.children[2].children[6];
  assert.match(decision.children[3].textContent, /Policy\/HITL/);
  assert.match(decision.children[4].textContent, /Source déclarée : SYNTHETIC/);
  assert.match(decision.children[4].textContent, /Horodatage déclaré : not verified/);
});

test('synthetic: null, undefined and primitive payloads fail closed to UNKNOWN', () => {
  for (const payload of [null, undefined, false, 0, 'SYNTHETIC malformed response']) {
    const steps = describeSanPaymentsJourney(payload);
    assert.equal(steps.length, 8);
    assert.ok(steps.every(step => step.state === 'UNKNOWN' && !step.isOperationalClaim));
  }
});

test('synthetic: rendering with null response retains eight accessible UNKNOWN steps', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { children: [], append(node) { this.children.push(node); } };
  const nav = renderSanPaymentsJourney(document, root, null);
  assert.equal(nav.tag, 'nav');
  assert.ok(nav.attributes['aria-label']);
  const list = nav.children[2];
  assert.equal(list.tag, 'ol');
  assert.equal(list.children.length, 8);
  assert.ok(list.children.every(item => item.attributes['data-state'] === 'UNKNOWN'));
});

test('synthetic: throwing record getter fails closed without hiding other stages', () => {
  const records = {
    get incident() { throw new Error('SYNTHETIC adapter failure'); },
    impact: { state: 'BLOCKED', source: 'SYNTHETIC' }
  };
  const steps = describeSanPaymentsJourney(records);
  assert.equal(steps.length, 8);
  assert.equal(steps[0].state, 'UNKNOWN');
  assert.equal(steps[1].state, 'BLOCKED');
  assert.equal(steps[1].source, 'SYNTHETIC');
});

test('synthetic: throwing metadata getter cannot publish partial AVAILABLE claim', () => {
  const records = {
    decision: {
      state: 'AVAILABLE',
      detail: 'SYNTHETIC unverified',
      get source() { throw new Error('SYNTHETIC metadata failure'); }
    },
    result: { state: 'BLOCKED' }
  };
  const steps = describeSanPaymentsJourney(records);
  assert.equal(steps[6].state, 'UNKNOWN');
  assert.equal(steps[6].detail, 'Aucune information vérifiée');
  assert.equal(steps[7].state, 'BLOCKED');
  assert.ok(steps.every(step => !step.isOperationalClaim));
});

test('synthetic: hostile Proxy and array records cannot crash rendering', () => {
  const records = new Proxy({}, {
    getOwnPropertyDescriptor() { throw new Error('SYNTHETIC proxy failure'); }
  });
  const steps = describeSanPaymentsJourney(records);
  assert.ok(steps.every(step => step.state === 'UNKNOWN'));
  assert.equal(describeSanPaymentsJourney({ run: [{ state: 'AVAILABLE' }] })[3].state, 'UNKNOWN');
});

test('synthetic: every stage has a separate explicit text status for screen readers', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { append() {} };
  const nav = renderSanPaymentsJourney(document, root, {
    incident: { state: 'LOADING' }, decision: { state: 'BLOCKED' }
  });
  const items = nav.children[2].children;
  assert.equal(items.length, 8);
  assert.equal(items[0].children[1].textContent, 'État : LOADING');
  assert.equal(items[6].children[1].textContent, 'État : BLOCKED');
  assert.equal(items[7].children[1].textContent, 'État : UNKNOWN');
  assert.ok(items.every(item => item.children[1].tag === 'span'));
});

test('synthetic: AVAILABLE is visibly consultable but never validated or READY', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { append() {} };
  const nav = renderSanPaymentsJourney(document, root, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC', observedAt: 'not verified' },
    decision: { state: 'BLOCKED' }
  });
  const items = nav.children[2].children;
  assert.equal(items[0].children[1].textContent,
    'État : AVAILABLE (données consultables, non validées)');
  assert.equal(items[6].children[1].textContent, 'État : BLOCKED');
  assert.equal(items[7].children[1].textContent, 'État : UNKNOWN');
  assert.match(items[0].children[4].textContent, /Source déclarée : SYNTHETIC/);
  assert.ok(describeSanPaymentsJourney({ incident: { state: 'AVAILABLE' } })
    .every(step => step.isOperationalClaim === false));
});
