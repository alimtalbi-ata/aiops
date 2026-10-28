// Browser behavior tested with a synthetic DOM, not a live portal.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const script = fs.readFileSync(new URL("../app/portal/portal_bootstrap_client.js", import.meta.url), "utf8");

function harness(fetchImpl) {
  class Element {
    constructor() {
      this.children = [];
      this.textContent = "";
      this.value = "";
      this.colSpan = 0;
    }
    replaceChildren(...children) { this.children = [...children]; }
    appendChild(child) { this.children.push(child); }
  }
  const ids = new Map();
  const metrics = new Map();
  for (const id of ["portal-read-token", "portal-runs", "portal-twin",
                    "portal-states", "portal-read-result"]) ids.set(id, new Element());
  for (const key of ["open_p1", "open_incidents", "running", "blocked",
                     "twin_nodes", "degraded_nodes"]) metrics.set(key, new Element());
  const document = {
    getElementById: (id) => ids.get(id) ?? null,
    querySelector: (selector) => metrics.get(selector.match(/data-metric="([^"]+)"/)?.[1]) ?? null,
    createElement: () => new Element()
  };
  const window = {};
  vm.runInNewContext(script, {document, window, fetch: fetchImpl});
  return {window, ids, metrics};
}

test("one-shot Bearer read uses no credentials or cache; DOM is text-only", async () => {
  const calls = [];
  const h = harness(async (url, options) => {
    calls.push({url, options});
    assert.equal(h.ids.get("portal-read-token").value, "");
    return {ok: true, json: async () => ({
      states: {dashboard: "READABLE_UNVERIFIED", runs: "READABLE_UNVERIFIED",
               twin: "READABLE_UNVERIFIED"},
      dashboard: {open_p1: 2, open_incidents: 4, running: 0, blocked: 0,
                  twin_nodes: 3, degraded_nodes: 1},
      runs: {items: [{run_id: "<img src=x onerror=alert(1)>", mode: "DEMO",
                     status: "BLOCKED"}]},
      twin: {nodes: 3, edges: 2, secret: "DO_NOT_RENDER"}
    })};
  });
  h.ids.get("portal-read-token").value = "synthetic-test-only-token";
  await h.window.loadPortalReadModel();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "/api/portal/bootstrap");
  assert.equal(calls[0].options.headers.Authorization, "Bearer synthetic-test-only-token");
  assert.equal(calls[0].options.credentials, "omit");
  assert.equal(calls[0].options.cache, "no-store");
  assert.equal(calls[0].options.redirect, "error");
  assert.equal(h.metrics.get("open_p1").textContent, "2");
  assert.equal(h.ids.get("portal-runs").children[0].children[0].textContent,
               "<img src=x onerror=alert(1)>");
  assert.ok(!h.ids.get("portal-twin").textContent.includes("DO_NOT_RENDER"));
  h.window.clearPortalReadModel();
  assert.equal(h.metrics.get("open_p1").textContent, "UNKNOWN");
  assert.equal(h.ids.get("portal-read-token").value, "");
});

test("denied and missing tokens never render stale data", async () => {
  let calls = 0;
  const h = harness(async () => { calls++; return {ok: false, status: 401}; });
  await h.window.loadPortalReadModel();
  assert.equal(calls, 0);
  h.ids.get("portal-read-token").value = "bad-token";
  await h.window.loadPortalReadModel();
  assert.equal(calls, 1);
  assert.equal(h.metrics.get("open_p1").textContent, "UNKNOWN");
  assert.match(h.ids.get("portal-read-result").textContent, /UNKNOWN/);
});

test("clear invalidates a pending response before it can render", async () => {
  let resolve;
  const h = harness(() => new Promise((done) => { resolve = done; }));
  h.ids.get("portal-read-token").value = "synthetic-token";
  const pending = h.window.loadPortalReadModel();
  h.window.clearPortalReadModel();
  resolve({ok: true, json: async () => ({states: {dashboard: "READABLE_UNVERIFIED"},
                                        dashboard: {open_p1: 99}})});
  await pending;
  assert.equal(h.metrics.get("open_p1").textContent, "UNKNOWN");
});
