/* ACME SIM-GLPI browser readback: no human ALLOW from forged 200. */
const test = require("node:test");
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");
const path = require("node:path");

const script = fs.readFileSync(
  path.join(__dirname, "../app/portal/acme_sim_glpi_client.js"), "utf8");
const ATTEMPT = "ACME-SIM-ABCDEF1234567890";
const GOOD = {
  schema: "aiops.portal.sim-glpi-readback.v1",
  state: "RESOLVED", authority: "SIMULATED_ONLY", ticket_authority: "SIMULATED_ONLY", simulated: true, tenant_id: "ACME-TEST",
  scenario_id: "ACME-SAN-PAYMENTS", attempt_id: ATTEMPT, mode: "SIMULATION",
  provenance: "SIMULATED", readback_source: "CORE_AND_WORKER_INDEPENDENT_SANDBOX_GET",
  worker_receipt_status: "SIMULATED_NO_EFFECT",
  worker_receipt_phase: "PRE_RESOLUTION", worker_no_effect_verified: true,
  core_resolution_after_worker_verified: true,
  terminal_ticket_digest_verified: true, independent_final_read_rounds: 2,
  source_freshness: "UNKNOWN", observed_at: null, human_allow: false,
  native_glpi_readmy_attested: false, real_glpi_writes_allowed: false,
  live_effects_allowed: false, host_e2e_qualified: false,
  ticket: {id: "SIM-GLPI-ABCDEF1234567890", status: "RESOLVED",
    current_state: "RESOLVED", transition_history_attested: false},
  incident_id: "INC-ACME-SIM-1234", run_id: "RUN-ACME-SIM-1234"
};
function setup(response) {
  const ids = ["sim-read", "sim-clear", "sim-attempt", "sim-token",
    "sim-status", "sim-ticket", "sim-state", "sim-run", "sim-transition",
    "sim-provenance", "sim-worker"];
  const nodes = Object.fromEntries(ids.map(id => [id, {
    value: "", textContent: "", disabled: false,
    addEventListener(type, handler) { this[type] = handler; }
  }]));
  nodes["sim-attempt"].value = ATTEMPT;
  nodes["sim-token"].value = "viewer-ci-only";
  let calls = [];
  const fetch = async (...args) => {
    calls.push(args);
    if (response instanceof Error) throw response;
    return {status: response.status, json: async () => response.body};
  };
  vm.runInNewContext(script, {
    document: {getElementById: id => nodes[id]},
    fetch, encodeURIComponent
  });
  return {nodes, calls};
}

test("strict resolved Core sandbox response renders SIMULATED, never human ALLOW", async () => {
  const {nodes, calls} = setup({status: 200, body: GOOD});
  await nodes["sim-read"].click();
  assert.equal(nodes["sim-ticket"].textContent, GOOD.ticket.id);
  assert.match(nodes["sim-state"].textContent, /RESOLVED · SIMULATED/);
  assert.match(nodes["sim-transition"].textContent, /NOT_ATTESTED/);
  assert.match(nodes["sim-provenance"].textContent, /GLPI humain UNKNOWN/);
  assert.match(nodes["sim-worker"].textContent, /SIMULATED_NO_EFFECT/);
  assert.equal(nodes["sim-token"].value, "");
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], "/api/demo/acme-sim-glpi/" + ATTEMPT);
  assert.equal(calls[0][1].credentials, "omit");
  assert.equal(calls[0][1].method, "GET");
  assert.equal(calls[0][1].redirect, "error");
});

test("forged HTTP 200 cannot promote wrong tenant, real ticket or human ALLOW", async () => {
  for (const mutation of [
    {tenant_id: "ACME-PROD"}, {human_allow: true},
    {authority: "NATIVE_GLPI"}, {ticket_authority: "REAL_GLPI"},
    {ticket: {...GOOD.ticket, id: "GLPI-123"}},
    {ticket: {...GOOD.ticket, transition_history_attested: true}},
    {state: "OPEN"}, {run_id: null}, {host_e2e_qualified: true},
    {provenance: "REAL"}, {real_glpi_writes_allowed: true},
    {native_glpi_readmy_attested: true}, {attempt_id: "ACME-SIM-OTHER123456"},
    {worker_receipt_status: "SUCCESS"},
    {worker_receipt_phase: "POST_RESOLUTION"},
    {worker_no_effect_verified: false},
    {core_resolution_after_worker_verified: false},
    {terminal_ticket_digest_verified: false},
    {independent_final_read_rounds: 1},
    {ticket: {...GOOD.ticket, current_state: "PREPARED"}}
  ]) {
    const {nodes} = setup({status: 200, body: {...GOOD, ...mutation}});
    await nodes["sim-read"].click();
    assert.equal(nodes["sim-ticket"].textContent, "UNKNOWN");
    assert.equal(nodes["sim-worker"].textContent, "UNKNOWN — aucun reçu no-effect");
    assert.match(nodes["sim-status"].textContent, /503 UNKNOWN/);
  }
});

test("forged 200 extra human, tenant ACL or LIVE claims never render RESOLVED", async () => {
  const topLevel = [
    {human_approved: true}, {idp_issuer: "forged-idp"},
    {native_glpi_read: "ALLOW"}, {ticket_user_readmy: "ALLOW"},
    {actor_acl_verified: true}, {tenant_acl_verified: true},
    {live_executor: "AUTHORIZED"}, {internal_service_token: "forged"},
    {worker_receipt_sha256: "a".repeat(64)},
    {terminal_ticket_sha256: "b".repeat(64)}
  ];
  for (const injection of topLevel) {
    const {nodes} = setup({status: 200, body: {...GOOD, ...injection}});
    await nodes["sim-read"].click();
    assert.equal(nodes["sim-ticket"].textContent, "UNKNOWN");
    assert.match(nodes["sim-status"].textContent, /503 UNKNOWN/);
  }
  for (const ticket of [
    {...GOOD.ticket, real_glpi_id: 42},
    {...GOOD.ticket, human_readmy: "ALLOW"},
    {...GOOD.ticket, idp_subject: "forged-user"}
  ]) {
    const {nodes} = setup({status: 200, body: {...GOOD, ticket}});
    await nodes["sim-read"].click();
    assert.equal(nodes["sim-state"].textContent, "UNKNOWN");
    assert.match(nodes["sim-status"].textContent, /503 UNKNOWN/);
  }
});

test("401, 403, 503 and network errors clear any ticket", async () => {
  for (const status of [401, 403, 503, 302]) {
    const {nodes} = setup({status, body: GOOD});
    await nodes["sim-read"].click();
    assert.equal(nodes["sim-ticket"].textContent, "UNKNOWN");
    assert.match(nodes["sim-status"].textContent, /(401|403|503)/);
  }
  const {nodes} = setup(new Error("offline"));
  await nodes["sim-read"].click();
  assert.equal(nodes["sim-ticket"].textContent, "UNKNOWN");
});

test("invalid attempt and missing viewer never issue business GET", async () => {
  const {nodes, calls} = setup({status: 200, body: GOOD});
  nodes["sim-attempt"].value = "REAL-GLPI-42";
  await nodes["sim-read"].click();
  assert.equal(calls.length, 0);
  nodes["sim-attempt"].value = ATTEMPT;
  nodes["sim-token"].value = "";
  await nodes["sim-read"].click();
  assert.equal(calls.length, 0);
  nodes["sim-clear"].click();
  assert.equal(nodes["sim-attempt"].value, "");
  assert.equal(nodes["sim-ticket"].textContent, "UNKNOWN");
});
