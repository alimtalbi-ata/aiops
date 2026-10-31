const test = require('node:test');
const assert = require('node:assert/strict');
const { routeFor, mount } = require('../app/portal/portal_run_link_client.js');

test('exact canonical run ID produces only a local deep link', () => {
  assert.equal(routeFor('RUN-73AFC6FF9315376C'), '/runs/RUN-73AFC6FF9315376C');
  for (const bad of ['', 'RUN-../evil', 'RUN-foo?token=secret', 'INC-123', 'RUN-<script>', null]) {
    assert.equal(routeFor(bad), null);
  }
});

test('legacy HTTP 200 cannot authorize a Run or mint browser credentials', async () => {
  const nodes = {
    'run-detail-id': { value: 'RUN-ACME-001' },
    'portal-read-token': { value: 'one-time-token' },
    'run-detail-open': { addEventListener: (event, cb) => { nodes.click = cb; } },
    'run-detail-error': { textContent: '' }
  };
  const paths = [];
  const requests = [];
  const requestSession = async (url, options) => {
    requests.push({ url, options, tokenInputAtRequest: nodes['portal-read-token'].value });
    return { ok: true, status: 200 };
  };
  assert.equal(mount({ getElementById: id => nodes[id] }, path => paths.push(path), requestSession), true);
  await nodes.click();
  assert.equal(nodes['portal-read-token'].value, '');
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, '/api/portal/run-session');
  assert.equal(requests[0].options.method, 'POST');
  assert.equal(requests[0].options.headers.Authorization, 'Bearer one-time-token');
  assert.equal(requests[0].options.headers['X-Portal-Run-ID'], 'RUN-ACME-001');
  assert.equal(requests[0].options.credentials, 'omit');
  assert.equal(requests[0].tokenInputAtRequest, '');
  assert.deepEqual(paths, []);
  assert.match(nodes['run-detail-error'].textContent, /UNKNOWN.*ACL acteur\+tenant absente/);
});

test('forged or stale 2xx responses never trigger Run navigation', async () => {
  for (const status of [200, 201, 202, 204, 206]) {
    const nodes = {
      'run-detail-id': { value: 'RUN-FOREIGN-001' },
      'portal-read-token': { value: 'viewer-bearer' },
      'run-detail-open': { addEventListener: (event, cb) => { nodes.click = cb; } },
      'run-detail-error': { textContent: '' }
    };
    const paths = [];
    const calls = [];
    mount({ getElementById: id => nodes[id] }, path => paths.push(path),
          async (url, options) => {
            calls.push({url, options});
            return {ok: true, status, json: async () => ({
              tenant_acl_qualified: true, actor_identity_server_derived: true,
              run_id: 'RUN-FOREIGN-001', state: 'CONNECTED'
            })};
          });
    await nodes.click();
    assert.deepEqual(paths, [], 'HTTP ' + status + ' must not navigate');
    assert.equal(calls.length, 1);
    assert.equal(calls[0].options.credentials, 'omit');
    assert.equal(nodes['portal-read-token'].value, '');
    assert.match(nodes['run-detail-error'].textContent, /UNKNOWN.*ACL acteur\+tenant absente/);
  }
});

test('invalid Run ID never exchanges the token or navigates', async () => {
  const nodes = {
    'run-detail-id': { value: 'RUN-../foreign' },
    'portal-read-token': { value: 'one-time-token' },
    'run-detail-open': { addEventListener: (event, cb) => { nodes.click = cb; } },
    'run-detail-error': { textContent: '' }
  };
  let calls = 0;
  const paths = [];
  mount({ getElementById: id => nodes[id] }, path => paths.push(path), async () => { calls++; return {ok:true}; });
  await nodes.click();
  assert.equal(calls, 0);
  assert.equal(paths.length, 0);
  assert.equal(nodes['run-detail-error'].textContent, 'UNKNOWN — identifiant Run invalide');
  assert.equal(nodes['portal-read-token'].value, '');
});

test('missing read token and failed session exchange do not navigate', async () => {
  const nodes = {
    'run-detail-id': { value: 'RUN-ACME-001' },
    'portal-read-token': { value: '' },
    'run-detail-open': { addEventListener: (event, cb) => { nodes.click = cb; } },
    'run-detail-error': { textContent: '' }
  };
  let calls = 0;
  const paths = [];
  mount({ getElementById: id => nodes[id] }, path => paths.push(path), async () => { calls++; return {ok:false,status:401}; });
  await nodes.click();
  assert.equal(calls, 0);
  nodes['portal-read-token'].value = 'wrong';
  await nodes.click();
  assert.equal(calls, 1);
  assert.equal(paths.length, 0);
  assert.equal(nodes['run-detail-error'].textContent, 'UNAUTHORIZED (HTTP 401) — jeton lecture invalide');
});

test('HTTP 403 and 503 remain visible and never navigate', async () => {
  for (const [status, expected] of [
    [403, 'UNAUTHORIZED (HTTP 403) — session lecture seule refusée'],
    [503, 'UNKNOWN (HTTP 503) — ACL acteur+tenant non qualifiée']
  ]) {
    const nodes = {
      'run-detail-id': { value: 'RUN-ACME-001' },
      'portal-read-token': { value: 'one-time-token' },
      'run-detail-open': { addEventListener: (event, cb) => { nodes.click = cb; } },
      'run-detail-error': { textContent: '' }
    };
    const paths = [];
    mount({ getElementById: id => nodes[id] }, path => paths.push(path),
          async () => ({ ok: false, status }));
    await nodes.click();
    assert.equal(nodes['run-detail-error'].textContent, expected);
    assert.equal(nodes['portal-read-token'].value, '');
    assert.deepEqual(paths, []);
  }
});

test('no credential persistence or browser cookie access is used', () => {
  const nodes = {
    'run-detail-id': { value: 'RUN-ACME-001' },
    'portal-read-token': { value: 'secret' },
    'run-detail-open': { addEventListener: () => {} },
    'run-detail-error': { textContent: '' }
  };
  const fs = require('node:fs');
  const source = fs.readFileSync(require.resolve('../app/portal/portal_run_link_client.js'), 'utf8');
  for (const forbidden of ['localStorage', 'sessionStorage', 'document.cookie', 'token=']) {
    assert.equal(source.includes(forbidden), false);
  }
  assert.equal(mount({ getElementById: id => nodes[id] }, () => {}, async () => ({ok:true})), true);
});

test('missing existing Portal controls do not create a parallel UI', () => {
  assert.equal(mount({ getElementById: () => null }, () => { throw Error('unexpected'); }, null), false);
});

test('bootstrap UI keeps 401/403/503 visible and never renders unscoped records', async () => {
  const fs = require('node:fs');
  const vm = require('node:vm');
  const source = fs.readFileSync(
    require.resolve('../app/portal/portal_bootstrap_client.js'), 'utf8');
  for (const [status, expected] of [
    [401, 'UNAUTHORIZED (HTTP 401)'],
    [403, 'UNAUTHORIZED (HTTP 403)'],
    [503, 'UNKNOWN (HTTP 503)']
  ]) {
    const nodes = {
      'portal-read-token': { value: 'test-only-viewer-token' },
      'portal-read-result': { textContent: '' }
    };
    const window = {};
    const document = {
      getElementById: id => nodes[id] || null,
      querySelector: () => null
    };
    let calls = 0;
    vm.runInNewContext(source, { window, document, fetch: async () => {
      calls += 1;
      return { ok: false, status };
    } });
    await window.loadPortalReadModel();
    assert.equal(calls, 1);
    assert.equal(nodes['portal-read-token'].value, '');
    assert.ok(nodes['portal-read-result'].textContent.includes(expected));
  }
});
