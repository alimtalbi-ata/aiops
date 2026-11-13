import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney } from './san_payments_journey.mjs';

// Offline semantic-DOM contract only; not a browser, tenant ACL, or LIVE proof.
const doc = { createElement(tag) {
  return { tag, attributes: {}, children: [], textContent: '',
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...nodes) { this.children.push(...nodes); } };
} };

test('spoofed timestamp controls fail closed independently of source provenance', () => {
  for (const observedAt of [
    '2026-11-13T20:00:00Z\\u202e',
    '2026-11-13T20:00:00Z\\u0000',
    '2026-11-13T20:00:00Z\\u200b'
  ].map(value => value.replace(/\\u([0-9a-f]{4})/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16))))) {
    const nav = renderSanPaymentsJourney(doc, { append() {} }, {
      incident: { state: 'AVAILABLE', source: 'SYNTHETIC:fixture', observedAt }
    }, { mode: 'DEMO' });
    const incident = nav.children[2].children[0];
    assert.equal(nav.attributes['data-mode'], 'DEMO');
    assert.equal(incident.attributes['data-state'], 'AVAILABLE');
    assert.equal(incident.attributes['data-provenance'], 'SYNTHETIC');
    assert.equal(incident.attributes['data-freshness'], 'UNKNOWN');
    assert.match(incident.children[4].textContent, /FRAÎCHEUR INCONNUE/);
    assert.match(nav.children[3].textContent, /8 horodatage\\(s\\) inconnu\\(s\\)/);
  }
});
