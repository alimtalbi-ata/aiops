import test from 'node:test';
import assert from 'node:assert/strict';
import { describeSanPaymentsJourney, renderSanPaymentsJourney } from './san_payments_journey.mjs';

// Offline synthetic DOM contract, not a browser or LIVE attestation.
const document = { createElement(tag) {
  return { tag, attributes: {}, children: [], textContent: '',
    setAttribute(k, v) { this.attributes[k] = v; },
    append(...items) { this.children.push(...items); } };
} };

test('synthetic: bidi overrides cannot visually forge source or freshness', () => {
  const records = { incident: {
    state: 'AVAILABLE',
    source: 'SYNTHETIC\u202eEVIL\u202c',
    observedAt: '2026-11-13\u2066LIVE\u2069',
    detail: 'text\u0000\u001bclean'
  }, decision: { state: 'BLOCKED' } };
  const steps = describeSanPaymentsJourney(records);
  assert.equal(steps.length, 8);
  for (const field of ['source', 'observedAt', 'detail']) {
    assert.doesNotMatch(steps[0][field], /[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/);
  }
  assert.equal(steps[0].source, 'SYNTHETIC EVIL');
  assert.equal(steps[6].state, 'BLOCKED');
  const nav = renderSanPaymentsJourney(document, { append() {} }, records, { mode: 'DEMO' });
  assert.equal(nav.attributes['data-mode'], 'DEMO');
  assert.equal(nav.children[2].children[0].attributes['data-provenance'], 'SYNTHETIC');
  assert.match(nav.children[2].children[0].children[4].textContent, /DONNÉES SYNTHÉTIQUES/);
  assert.equal(nav.children[2].children.length, 8);
});

test('synthetic: control-only provenance remains incomplete, not verified', () => {
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE', source: '\u202e\u0000', observedAt: '\u2066\u2069' }
  }, { mode: 'LIVE' });
  const item = nav.children[2].children[0];
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  assert.equal(item.attributes['data-provenance'], 'INCOMPLETE');
  assert.equal(item.attributes['data-freshness'], 'UNKNOWN');
  assert.match(item.children[4].textContent, /PROVENANCE INCOMPLÈTE/);
  assert.match(item.children[4].textContent, /FRAÎCHEUR INCONNUE/);
  assert.match(item.children[1].textContent, /non validées/);
});
