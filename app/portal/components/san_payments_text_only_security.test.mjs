import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney } from './san_payments_journey.mjs';

function strictDocument() {
  return {
    createElement(tag) {
      const node = { tag, attributes: {}, children: [], textContent: '',
        setAttribute(name, value) { this.attributes[name] = value; },
        append(...items) { this.children.push(...items); } };
      Object.defineProperty(node, 'innerHTML', {
        set() { throw new Error('Untrusted markup must never be interpreted'); }
      });
      return node;
    }
  };
}

test('hostile adapter strings remain text-only and never claim LIVE', () => {
  const payload = '<img src=x onerror=alert(1)>';
  const nav = renderSanPaymentsJourney(strictDocument(), { append() {} }, {
    incident: {
      state: 'AVAILABLE', detail: payload,
      source: 'SYNTHETIC: ' + payload,
      observedAt: '2026-11-12T00:00:00Z'
    }
  }, { mode: 'LIVE' });
  const incident = nav.children[2].children[0];
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  assert.equal(incident.attributes['data-state'], 'UNKNOWN');
  assert.equal(incident.attributes['data-adapter-state'], 'AVAILABLE');
  assert.equal(incident.attributes['data-trust-state'], 'UNVERIFIED');
  assert.equal(incident.attributes['data-provenance'], 'SYNTHETIC');
  assert.equal(incident.children[2].textContent, payload);
  assert.match(incident.children[4].textContent, /DONNÉES SYNTHÉTIQUES/);
  assert.match(incident.children[4].textContent, /<img src=x onerror=alert\(1\)>/);
  assert.doesNotMatch(nav.children[1].textContent, /Mode : LIVE/);
});

test('all eight stages remain unverified even when adapters declare AVAILABLE', () => {
  const ids = ['incident', 'impact', 'noc', 'run', 'evidence', 'policy', 'decision', 'result'];
  const records = Object.fromEntries(ids.map(id => [id, {
    state: 'AVAILABLE', source: 'adapter', observedAt: '2026-11-12T00:00:00Z'
  }]));
  const nav = renderSanPaymentsJourney(strictDocument(), { append() {} }, records, { mode: 'DEMO' });
  assert.equal(nav.children[2].children.length, 8);
  for (const item of nav.children[2].children) {
    assert.equal(item.attributes['data-state'], 'UNKNOWN');
    assert.equal(item.attributes['data-trust-state'], 'UNVERIFIED');
  }
});
