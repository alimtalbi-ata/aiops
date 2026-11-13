import test from 'node:test';
import assert from 'node:assert/strict';
import { describeSanPaymentsJourney, renderSanPaymentsJourney } from './san_payments_journey.mjs';

// Synthetic DOM contract only; not a browser, authorization or LIVE qualification.
function documentStub() {
  return { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(key, value) { this.attributes[key] = value; },
      append(...children) { this.children.push(...children); } };
  } };
}

test('synthetic: inherited adapter claims cannot promote any step or mode to LIVE', () => {
  const forged = Object.create({
    incident: { state: 'AVAILABLE', source: 'LIVE', observedAt: '2026-11-13' }
  });
  const steps = describeSanPaymentsJourney(forged);
  assert.equal(steps.length, 8);
  assert.equal(steps[0].state, 'UNKNOWN');
  assert.equal(steps[0].source, 'Source non renseignée');
  assert.equal(steps[0].observedAt, 'Fraîcheur inconnue');
  const options = Object.create({ mode: 'DEMO' });
  const nav = renderSanPaymentsJourney(documentStub(), { append() {} }, forged, options);
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  assert.match(nav.children[1].textContent, /LIVE non revendiqué/);
  assert.equal(nav.children[2].tag, 'ol');
  assert.equal(nav.children[2].children.length, 8);
});

test('synthetic: hostile inherited records and forged LIVE flags remain unverified', () => {
  const record = Object.assign(Object.create({
    state: 'AVAILABLE', source: 'LIVE', observedAt: '2026-11-13'
  }), { detail: 'Claimed healthy', isOperationalClaim: true });
  const nav = renderSanPaymentsJourney(documentStub(), { append() {} }, {
    incident: record,
    result: { state: 'BLOCKED', source: 'SYNTHETIC', observedAt: 'unknown' }
  }, { mode: 'LIVE' });
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  const stages = nav.children[2].children;
  assert.equal(stages[0].attributes['data-state'], 'UNKNOWN');
  assert.equal(stages[0].attributes['data-provenance'], 'INCOMPLETE');
  assert.equal(stages[7].attributes['data-state'], 'BLOCKED');
  assert.equal(stages[7].attributes['data-provenance'], 'SYNTHETIC');
  assert.equal(stages.length, 8);
});
