// In-process DOM unit tests, not a browser or live service integration.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";

const script = readFileSync(new URL("../app/portal/operator_console.js", import.meta.url), "utf8");
const ids = ["access", "clear", "token", "auth-state", "role-state",
  "incidents-state", "incidents-items", "runs-state", "runs-items",
  "evidence-state", "evidence-items"];

function mount(fetcher) {
  class Element {
    constructor() { this.value = ""; this.textContent = ""; this.children = []; this.events = {}; }
    addEventListener(name, callback) { this.events[name] = callback; }
    replaceChildren() { this.children = []; }
    appendChild(child) { this.children.push(child); }
    fire(name) { this.events[name]({ preventDefault() {} }); }
  }
  const nodes = Object.fromEntries(ids.map(id => [id, new Element()]));
  const win = { events: {}, addEventListener(name, callback) { this.events[name] = callback; } };
  const doc = { getElementById: id => nodes[id], createElement: () => new Element() };
  runInNewContext(script, { document: doc, window: win, fetch: fetcher });
  return { nodes, win, submit(token) { nodes.token.value = token; nodes.access.fire("submit"); } };
}
const flush = () => new Promise(resolve => setImmediate(resolve));
function snapshot(overrides = {}) {
  return {
    schema: "aiops.portal.operator-read.v1",
    provenance: "UNATTESTED_UPSTREAM_API_READ",
    runtime_authenticated: false,
    live_remediation_authorized: false,
    role: "viewer",
    states: { incidents: "READABLE_UNVERIFIED", runs: "UNKNOWN", evidence: "FORBIDDEN_BY_ROLE" },
    resources: {
      incidents: { items: [{ incident_id: "INC-1", title: "<img src=x onerror=alert(1)>", payload: "SECRET" }] },
      runs: null, evidence: null
    },
    ...overrides
  };
}
const response = data => ({ ok: true, status: 200, json: async () => data });

test("viewer renders only whitelisted text and never stores token in field", async () => {
  let options;
  const ui = mount(async (url, opts) => {
    assert.equal(url, "/api/portal/operator/snapshot");
    options = opts;
    return response(snapshot());
  });
  ui.submit("v".repeat(40));
  await flush();
  assert.equal(ui.nodes.token.value, "");
  assert.equal(options.credentials, "omit");
  assert.equal(options.cache, "no-store");
  assert.equal(options.redirect, "error");
  assert.equal(ui.nodes["incidents-items"].children.length, 1);
  assert.match(ui.nodes["incidents-items"].children[0].textContent, /<img src=x/);
  assert.doesNotMatch(ui.nodes["incidents-items"].children[0].textContent, /SECRET/);
  assert.equal(ui.nodes["evidence-state"].textContent, "FORBIDDEN_BY_ROLE");
  assert.equal(ui.nodes["role-state"].textContent, "Rôle : viewer");
});

test("logout invalidates a pending response (no stale data after clear)", async () => {
  let resolveRequest;
  const ui = mount(() => new Promise(resolve => { resolveRequest = resolve; }));
  ui.submit("v".repeat(40));
  ui.nodes.clear.fire("click");
  resolveRequest(response(snapshot()));
  await flush();
  assert.equal(ui.nodes["incidents-items"].children.length, 0);
  assert.equal(ui.nodes["incidents-state"].textContent, "UNKNOWN");
  assert.equal(ui.nodes["auth-state"].textContent, "UNKNOWN — session effacée");
});

test("invalid provenance fails closed to UNKNOWN", async () => {
  const ui = mount(async () => response(snapshot({ runtime_authenticated: true })));
  ui.submit("v".repeat(40));
  await flush();
  assert.equal(ui.nodes["incidents-state"].textContent, "UNKNOWN");
  assert.match(ui.nodes["auth-state"].textContent, /UNKNOWN/);
});

test("HTTP 401 clears the token and never shows resource data", async () => {
  const ui = mount(async () => ({ ok: false, status: 401 }));
  ui.submit("v".repeat(40));
  await flush();
  assert.equal(ui.nodes.token.value, "");
  assert.equal(ui.nodes["incidents-items"].children.length, 0);
  assert.equal(ui.nodes["role-state"].textContent, "Rôle : UNKNOWN");
});

test("invalid or short token never invokes fetch", async () => {
  let count = 0;
  const ui = mount(async () => { count += 1; return response(snapshot()); });
  ui.submit("short");
  await flush();
  assert.equal(count, 0);
  assert.equal(ui.nodes["incidents-state"].textContent, "UNKNOWN");
});
