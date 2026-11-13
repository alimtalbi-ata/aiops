import test from 'node:test';
import assert from 'node:assert/strict';
import { renderSanPaymentsJourney } from './san_payments_journey.mjs';

// Synthetic DOM contract only; this is not a browser, tenant ACL or LIVE attestation.
function documentStub() {
  const created = [];
  return {
    created,
    createElement(tag) {
      const node = {
        tag, attributes: {}, children: [], textContent: '',
        setAttribute(name, value) { this.attributes[name] = value; },
        append(...children) { this.children.push(...children); }
      };
      created.push(node);
      return node;
    }
  };
}

test('synthetic: hostile metadata stays text-only, no DOM injection or LIVE mode promotion', () => {
  const document = documentStub();
  const root = { children: [], append(node) { this.children.push(node); } };
  const payload = '<img src=x onerror=alert(1)><script>evil()</script>';
  const nav = renderSanPaymentsJourney(document, root, {
    incident: { state: 'AVAILABLE', detail: payload, source: payload, observedAt: payload },
    decision: { state: 'BLOCKED', source: 'SYNTHETIC' }
  }, { mode: 'LIVE' });
  assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
  assert.equal(nav.children[2].children.length, 8);
  const incident = nav.children[2].children[0];
  assert.equal(incident.children[2].textContent, payload);
  assert.match(incident.children[4].textContent, /Source déclarée : <img/);
  assert.match(incident.children[4].textContent, /Horodatage déclaré : <img/);
  assert.equal(incident.attributes['data-provenance'], 'DECLARED_UNVERIFIED');
  assert.equal(incident.attributes['data-freshness'], 'DECLARED_UNVERIFIED');
  assert.equal(nav.children[2].children[6].attributes['data-state'], 'BLOCKED');
  assert.ok(document.created.every(node => !['script', 'img'].includes(node.tag)));
  assert.equal(root.children[0], nav);
});
