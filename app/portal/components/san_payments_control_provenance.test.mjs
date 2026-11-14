import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney } from './san_payments_journey.mjs';

function documentStub() {
  return { createElement(tag) {
    return {
      tag, attributes: {}, children: [], textContent: '',
      setAttribute(name, value) { this.attributes[name] = value; },
      append(...nodes) { this.children.push(...nodes); }
    };
  } };
}

test('control-obfuscated provenance is incomplete, never synthetic or LIVE-attested', () => {
  for (const source of ['SYN\u0000THETIC', 'LIVE\u001fvalidated', 'SYN\u0085THETIC']) {
    const nav = renderSanPaymentsJourney(documentStub(), { append() {} }, {
      incident: { state: 'AVAILABLE', source, observedAt: '2026-11-13T20:00:00Z' }
    }, { mode: 'DEMO' });
    const incident = nav.children[2].children[0];
    assert.equal(nav.attributes['data-mode'], 'DEMO');
    assert.equal(incident.attributes['data-provenance'], 'INCOMPLETE');
    assert.match(incident.children.at(-1).textContent, /PROVENANCE INCOMPLÈTE/);
    assert.match(nav.children.at(-1).textContent, /1 source\(s\) non renseignée\(s\)/);
  }
});

test('plain synthetic provenance remains visibly synthetic in REPLAY', () => {
  const nav = renderSanPaymentsJourney(documentStub(), { append() {} }, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC:fixture', observedAt: '2026-11-13T20:00:00Z' }
  }, { mode: 'REPLAY' });
  assert.equal(nav.children[2].children[0].attributes['data-provenance'], 'SYNTHETIC');
  assert.equal(nav.attributes['data-mode'], 'REPLAY');
});
