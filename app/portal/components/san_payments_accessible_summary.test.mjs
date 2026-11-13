import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney } from './san_payments_journey.mjs';

// Semantic DOM only: not a browser, accessibility audit or LIVE attestation.
function documentStub() {
  return { createElement(tag) {
    return {
      tag, attributes: {}, children: [], textContent: '',
      setAttribute(name, value) { this.attributes[name] = value; },
      append(...nodes) { this.children.push(...nodes); }
    };
  } };
}

test('French journey exposes a polite atomic summary in DEMO and REPLAY', () => {
  for (const mode of ['DEMO', 'REPLAY']) {
    const parent = { children: [], append(node) { this.children.push(node); } };
    const nav = renderSanPaymentsJourney(documentStub(), parent, {}, { mode });
    assert.equal(nav.attributes.lang, 'fr');
    assert.equal(nav.attributes['data-mode'], mode);
    assert.equal(parent.children[0], nav);
    const summary = nav.children.at(-1);
    assert.equal(summary.attributes.role, 'status');
    assert.equal(summary.attributes['aria-live'], 'polite');
    assert.equal(summary.attributes['aria-atomic'], 'true');
    assert.match(summary.textContent, /UNKNOWN : 8/);
    assert.match(summary.textContent, /pas un indicateur de santé/);
  }
});

test('unattested LIVE remains UNKNOWN with no success announcement', () => {
  const nav = renderSanPaymentsJourney(documentStub(), { append() {} }, {}, { mode: 'LIVE' });
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  assert.match(nav.children[1].textContent, /LIVE non revendiqué/);
  assert.match(nav.children.at(-1).textContent, /UNKNOWN : 8/);
});
