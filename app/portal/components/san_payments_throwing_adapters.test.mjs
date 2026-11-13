import test from 'node:test';
import assert from 'node:assert/strict';
import { describeSanPaymentsJourney, renderSanPaymentsJourney, SAN_PAYMENTS_STEPS } from './san_payments_journey.mjs';

// Offline semantic DOM only; not a browser, authorization or LIVE proof.
const dom = () => ({ createElement(tag) {
  return { tag, attributes: {}, children: [], textContent: '',
    setAttribute(key, value) { this.attributes[key] = value; },
    append(...nodes) { this.children.push(...nodes); } };
} });

test('throwing adapter fields cannot leave a partially trusted step', () => {
  const records = { incident: {
    state: 'AVAILABLE', detail: 'looks healthy',
    get source() { throw new Error('adapter unavailable'); }
  }};
  const steps = describeSanPaymentsJourney(records);
  assert.equal(steps.length, SAN_PAYMENTS_STEPS.length);
  assert.equal(steps[0].state, 'UNKNOWN');
  assert.equal(steps[0].source, 'Source non renseignée');
  assert.equal(steps[0].detail, 'Aucune information vérifiée');
  const nav = renderSanPaymentsJourney(dom(), { append() {} }, records, { mode: 'LIVE' });
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  assert.equal(nav.children[2].children[0].attributes['data-state'], 'UNKNOWN');
  assert.equal(nav.children[2].children[0].attributes['data-provenance'], 'INCOMPLETE');
});

test('throwing Proxy and mode accessor fail closed without breaking the journey', () => {
  const records = new Proxy({}, { getOwnPropertyDescriptor() { throw new Error('not authorized'); } });
  const options = { get mode() { throw new Error('untrusted mode'); } };
  const nav = renderSanPaymentsJourney(dom(), { append() {} }, records, options);
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  assert.equal(nav.children[2].children.length, 8);
  assert.ok(nav.children[2].children.every(item => item.attributes['data-state'] === 'UNKNOWN'));
  assert.match(nav.children[1].textContent, /LIVE non revendiqué/);
});

test('declared synthetic record never promotes a failed stage to operational LIVE', () => {
  const nav = renderSanPaymentsJourney(dom(), { append() {} }, {
    incident: { state: 'BLOCKED', source: 'SYNTHETIC:scenario', observedAt: '2026-11-13' }
  }, { mode: 'REPLAY' });
  assert.equal(nav.attributes['data-mode'], 'REPLAY');
  const incident = nav.children[2].children[0];
  assert.equal(incident.attributes['data-state'], 'BLOCKED');
  assert.equal(incident.attributes['data-provenance'], 'SYNTHETIC');
  assert.equal(incident.attributes['data-freshness'], 'DECLARED_UNVERIFIED');
  assert.match(incident.children[4].textContent, /DONNÉES SYNTHÉTIQUES/);
});
