const test = require('node:test');
const assert = require('node:assert/strict');
const { routeFor, mount } = require('../app/portal/portal_run_link_client.js');

test('exact canonical run ID produces only a local deep link', () => {
  assert.equal(routeFor('RUN-73AFC6FF9315376C'), '/runs/RUN-73AFC6FF9315376C');
  for (const bad of ['', 'RUN-../evil', 'RUN-foo?token=secret', 'INC-123', 'RUN-<script>', null]) {
    assert.equal(routeFor(bad), null);
  }
});

test('navigation is local and never fetches or handles a token', () => {
  const nodes = {
    'run-detail-id': { value: 'RUN-ACME-001' },
    'run-detail-open': { addEventListener: (event, cb) => { nodes.click = cb; } },
    'run-detail-error': { textContent: '' }
  };
  const paths = [];
  assert.equal(mount({ getElementById: id => nodes[id] }, path => paths.push(path)), true);
  nodes.click();
  assert.deepEqual(paths, ['/runs/RUN-ACME-001']);
  nodes['run-detail-id'].value = 'RUN-../foreign';
  nodes.click();
  assert.equal(nodes['run-detail-error'].textContent, 'UNKNOWN — identifiant Run invalide');
  assert.equal(paths.length, 1);
});

test('missing existing Portal controls do not create a parallel UI', () => {
  assert.equal(mount({ getElementById: () => null }, () => { throw Error('unexpected'); }), false);
});
