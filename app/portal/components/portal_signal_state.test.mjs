import test from 'node:test';
import assert from 'node:assert/strict';
import { describePortalSignal, renderPortalSignal } from './portal_signal_state.mjs';

test('synthetic: absent or invalid state remains UNKNOWN, freshness unproven', () => {
  for (const input of [{}, { state: 'READY', observedAt: null }, { state: 'HEALTHY' }]) {
    const result = describePortalSignal(input);
    assert.equal(result.state, 'UNKNOWN');
    assert.equal(result.freshnessLabel, 'Fraîcheur inconnue');
    assert.equal(result.isOperationalClaim, false);
  }
});

test('synthetic: BLOCKED and ERROR retain distinct actionable guidance', () => {
  assert.match(describePortalSignal({ state: 'BLOCKED' }).hint, /droits/);
  assert.match(describePortalSignal({ state: 'ERROR' }).hint, /Réessayez/);
});

test('synthetic: renders untrusted source as text only, with ARIA label', () => {
  const nodes = [];
  const doc = { createElement(tag) {
    const node = { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k,v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
    nodes.push(node);
    return node;
  }};
  const root = { children: [], append(node) { this.children.push(node); } };
  const section = renderPortalSignal(doc, root, {
    state: 'AVAILABLE', source: '<img src=x onerror=alert(1)>',
    observedAt: 'synthetic-2026-11-12'
  });
  assert.equal(section.attributes['aria-label'], 'État et provenance');
  assert.equal(section.children[2].textContent, '<img src=x onerror=alert(1)>');
  assert.equal(section.children[3].textContent, 'Horodatage déclaré : synthetic-2026-11-12');
  assert.equal(root.children.length, 1);
  assert.equal(nodes.length, 5);
});
