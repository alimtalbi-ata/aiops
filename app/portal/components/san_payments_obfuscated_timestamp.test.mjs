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
  for (const control of [0x202e, 0x0000, 0x200b]) {
    const observedAt = '2026-11-13T20:00:00Z' + String.fromCharCode(control);
    const nav = renderSanPaymentsJourney(doc, { append() {} }, {
      incident: { state: 'AVAILABLE', source: 'SYNTHETIC:fixture', observedAt }
    }, { mode: 'DEMO' });
    const incident = nav.children[2].children[0];
    assert.equal(nav.attributes['data-mode'], 'DEMO');
    assert.equal(incident.attributes['data-state'], 'AVAILABLE');
    assert.equal(incident.attributes['data-provenance'], 'SYNTHETIC');
    assert.equal(incident.attributes['data-freshness'], 'UNKNOWN');
    assert.match(incident.children[4].textContent, /FRAÎCHEUR INCONNUE/);
    assert.ok(nav.children[3].textContent.includes('8 horodatage(s) inconnu(s)'));
  }
});
