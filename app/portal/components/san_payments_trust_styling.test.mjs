import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney } from './san_payments_journey.mjs';

function stubDocument() {
  return { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(key, value) { this.attributes[key] = value; },
      append(...nodes) { this.children.push(...nodes); } };
  } };
}

test('AVAILABLE is consultable but never a trusted or LIVE styling claim', () => {
  for (const mode of ['DEMO', 'REPLAY', 'LIVE']) {
    const nav = renderSanPaymentsJourney(stubDocument(), { append() {} },
      { incident: { state: 'AVAILABLE', detail: 'Consultable', source: 'Adapter declared', observedAt: '2026-11-12T00:00:00Z' } },
      { mode });
    const item = nav.children[2].children[0];
    assert.equal(item.attributes['data-adapter-state'], 'AVAILABLE');
    assert.equal(item.attributes['data-state'], 'UNKNOWN');
    assert.equal(item.attributes['data-trust-state'], 'UNVERIFIED');
    assert.match(item.children[1].textContent, /consultables, non validées/);
    assert.notEqual(nav.attributes['data-mode'], 'LIVE');
  }
});

test('BLOCKED remains blocked without being promoted to trusted', () => {
  const nav = renderSanPaymentsJourney(stubDocument(), { append() {} },
    { policy: { state: 'BLOCKED' } }, { mode: 'DEMO' });
  const item = nav.children[2].children.find(node => node.attributes['data-step'] === 'policy');
  assert.equal(item.attributes['data-state'], 'BLOCKED');
  assert.equal(item.attributes['data-adapter-state'], 'BLOCKED');
  assert.equal(item.attributes['data-trust-state'], 'UNVERIFIED');
});
