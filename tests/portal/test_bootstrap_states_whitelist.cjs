// Isolated negative regression: extra unvalidated state must not promote the global result.
// Run: node --test tests/portal/test_bootstrap_states_whitelist.cjs
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const script = fs.readFileSync("app/portal/portal_bootstrap_client.js", "utf8");
function element() {
  return { value: "", textContent: "", children: [], appendChild(x) { this.children.push(x); },
    replaceChildren() { this.children = []; } };
}
test("S-022: unknown evidence/copilot state cannot promote UNKNOWN panels", async () => {
  const ids = new Map();
  for (const id of ["portal-read-token", "portal-runs", "portal-twin", "portal-states", "portal-read-result"])
    ids.set(id, element());
  ids.get("portal-read-token").value = "synthetic-token";
  const document = {
    getElementById: (id) => ids.get(id) || null,
    querySelector: () => null,
    createElement: () => element()
  };
  const payload = {
    schema: "aiops.portal.readmodels.v1", provenance: "UNATTESTED_UPSTREAM_API_READ",
    tenant_acl_qualified: true, actor_identity_server_derived: true,
    runtime_authenticated: false, live_remediation_authorized: false,
    states: { dashboard: "UNKNOWN", runs: "UNKNOWN", twin: "UNKNOWN",
      evidence: "READABLE_UNVERIFIED", copilot: "READABLE_UNVERIFIED" },
    dashboard: null, runs: null, twin: null
  };
  const window = {};
  vm.runInNewContext(script, { window, document, fetch: async () => ({
    ok: true, json: async () => payload
  }) });
  await window.loadPortalReadModel();
  assert.match(ids.get("portal-read-result").textContent, /^UNKNOWN/);
  assert.match(ids.get("portal-states").textContent, /dashboard: UNKNOWN/);
  assert.doesNotMatch(ids.get("portal-states").textContent, /evidence|copilot/);
});
