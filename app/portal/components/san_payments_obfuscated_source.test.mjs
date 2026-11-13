import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney } from './san_payments_journey.mjs';

// Synthetic semantic-DOM contract, not a browser or LIVE qualification.
const documentStub = { createElement(tag) {
  return { tag, attributes: {}, children: [], textContent: '',
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...nodes) { this.children.push(...nodes); } };
} };

test('format-control spoofing of source cannot escape incomplete provenance', () => {
  for (const source of ['SYN\u200bTHETIC:fixture', 'LI\u202eVE', '\u2066SYNTHETIC\u2069']) {
    const nav = renderSanPaymentsJourney(documentStub, { append() {} }, {
      incident: { state: 'AVAILABLE', source, observedAt: '2026-11-13T18:00:00Z' }
    }, { mode: 'DEMO' });
    const incident = nav.children[2].children[0];
    assert.equal(nav.attributes['data-mode'], 'DEMO');
    assert.equal(incident.attributes['data-provenance'], 'INCOMPLETE');
    assert.match(incident.children[4].textContent, /PROVENANCE INCOMPLÈTE/);
    assert.doesNotMatch(incident.children[4].textContent, /[\u200b-\u200f\u202a-\u202e\u2060\u2066-\u2069\ufeff]/);
    assert.match(nav.children[3].textContent, /1 source\(s\) non renseignée\(s\)/);
    assert.match(incident.children[1].textContent, /non validées/);
  }
});
