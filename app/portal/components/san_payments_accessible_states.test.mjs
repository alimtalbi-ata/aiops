import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney, SAN_PAYMENTS_STEPS } from './san_payments_journey.mjs';

// Offline semantic-DOM contract. Not a real browser, tenant ACL or LIVE attestation.
const dom = () => ({ createElement(tag) {
  return { tag, attributes: {}, children: [], textContent: '',
    setAttribute(name, value) { this.attributes[name] = value; },
    append(...nodes) { this.children.push(...nodes); } };
} });

test('all six declared step states retain accessible guidance without claiming LIVE', () => {
  const states = ['LOADING', 'EMPTY', 'ERROR', 'UNKNOWN', 'BLOCKED', 'AVAILABLE'];
  const records = Object.fromEntries(SAN_PAYMENTS_STEPS.map((step, i) => [
    step.id, { state: states[i] ?? 'UNKNOWN', source: 'SYNTHETIC:fixture' }
  ]));
  for (const mode of ['DEMO', 'REPLAY', 'LIVE', undefined]) {
    const parent = { append() {} };
    const nav = renderSanPaymentsJourney(dom(), parent, records, { mode });
    assert.equal(nav.tag, 'nav');
    assert.equal(nav.attributes['data-mode'], mode === 'DEMO' || mode === 'REPLAY' ? mode : 'UNKNOWN');
    assert.match(nav.attributes['aria-label'], /Parcours SAN vers Payments/);
    assert.match(nav.children[1].textContent, /aucune opération LIVE|LIVE non revendiqué/);
    const list = nav.children[2];
    assert.equal(list.tag, 'ol');
    assert.equal(list.children.length, 8);
    for (const [i, item] of list.children.entries()) {
      assert.equal(item.tag, 'li');
      assert.equal(item.attributes['data-step'], SAN_PAYMENTS_STEPS[i].id);
      assert.equal(item.children[0].textContent, SAN_PAYMENTS_STEPS[i].label);
      assert.ok(item.children[3].textContent.length > 0, 'state-specific operator guidance');
      assert.match(item.children[4].textContent, /DONNÉES SYNTHÉTIQUES/);
      assert.equal(item.attributes['data-freshness'], 'UNKNOWN');
      assert.equal(item.attributes['data-provenance'], 'SYNTHETIC');
      assert.equal(item.attributes['aria-busy'], i === 0 ? 'true' : undefined);
    }
    assert.match(nav.children[3].textContent, /pas un indicateur de santé/);
  }
});

test('malformed step states cannot become success, resolved or approved', () => {
  const records = Object.fromEntries(SAN_PAYMENTS_STEPS.map(step => [
    step.id, { state: 'APPROVED', source: 'LIVE', observedAt: '2026-11-13' }
  ]));
  const nav = renderSanPaymentsJourney(dom(), { append() {} }, records, { mode: 'LIVE' });
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  for (const item of nav.children[2].children) {
    assert.equal(item.attributes['data-state'], 'UNKNOWN');
    assert.equal(item.attributes['data-provenance'], 'INCOMPLETE');
    assert.equal(item.attributes['data-freshness'], 'UNKNOWN');
  }
});
