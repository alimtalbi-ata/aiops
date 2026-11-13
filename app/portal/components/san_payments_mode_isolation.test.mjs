import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney } from './san_payments_journey.mjs';

// Offline DOM contract: does not attest browser, tenant authorization, or LIVE.
const doc = () => ({ createElement(tag) {
  return { tag, attributes: {}, children: [], textContent: '',
    setAttribute(k, v) { this.attributes[k] = v; },
    append(...nodes) { this.children.push(...nodes); } };
} });

test('synthetic: every explicit presentation mode remains isolated from operational status', () => {
  for (const mode of ['DEMO', 'REPLAY', 'LIVE', 'UNKNOWN', '', null]) {
    const nav = renderSanPaymentsJourney(doc(), { append() {} }, {
      incident: { state: 'AVAILABLE', source: 'SYNTHETIC', observedAt: 'unverified' },
      decision: { state: 'BLOCKED' }
    }, { mode });
    const expected = mode === 'DEMO' || mode === 'REPLAY' ? mode : 'UNKNOWN';
    assert.equal(nav.attributes['data-mode'], expected);
    assert.match(nav.attributes['aria-label'], new RegExp('mode ' + expected));
    assert.match(nav.children[1].textContent, /aucune opération LIVE|LIVE non revendiqué/);
    const items = nav.children[2].children;
    assert.equal(items.length, 8);
    assert.equal(items[0].attributes['data-provenance'], 'SYNTHETIC');
    assert.equal(items[0].attributes['data-freshness'], 'DECLARED_UNVERIFIED');
    assert.equal(items[6].attributes['data-state'], 'BLOCKED');
    assert.equal(items[7].attributes['data-state'], 'UNKNOWN');
    assert.match(nav.children[3].textContent, /pas un indicateur de santé/);
  }
});

test('synthetic: hostile mode metadata fails closed while preserving independent stages', () => {
  const options = new Proxy({}, { getOwnPropertyDescriptor() { throw Error('synthetic inaccessible options'); } });
  const nav = renderSanPaymentsJourney(doc(), { append() {} }, {
    incident: { state: 'LOADING' },
    result: { state: 'BLOCKED', source: 'SYNTHETIC' }
  }, options);
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  assert.equal(nav.children[2].children[0].attributes['aria-busy'], 'true');
  assert.equal(nav.children[2].children[7].attributes['data-state'], 'BLOCKED');
  assert.equal(nav.children[2].children[7].attributes['data-provenance'], 'SYNTHETIC');
});
