// Synthetic DOM only: this is not a real browser or LIVE capture.
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const script = fs.readFileSync("app/portal/acme_explore_story_client.js", "utf8");
const flush = () => new Promise(resolve => setImmediate(resolve));

function harness(responder) {
  const elements = new Map();
  let scheduled = null;
  const requests = [];
  function element() {
    return {
      value: "", textContent: "", children: [], attributes: {}, listeners: {},
      addEventListener(name, cb) { this.listeners[name] = cb; },
      setAttribute(k, v) { this.attributes[k] = v; },
      replaceChildren() { this.children = []; },
      appendChild(child) { this.children.push(child); },
      click() { return this.listeners.click(); }
    };
  }
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    createElement() { return element(); }
  };
  const context = {
    document,
    fetch: async (url, options) => {
      requests.push({url, options});
      return responder(url, options);
    },
    setTimeout(fn) { scheduled = fn; return 1; },
    clearTimeout() { scheduled = null; }
  };
  vm.runInNewContext(script, context);
  return {get: document.getElementById, requests, timer: () => scheduled};
}

function envelope(action, mode, cursor, overrides = {}) {
  const timeline = [
    {cue: "detect", service: "grafana", view: "alert_dashboard",
      itil_practice: "monitoring_event_management", owner_role: "noc_l1",
      handoff: "monitoring_to_noc_l1", evidence_required: "source_event_id_observed_at",
      status: "MISSING"},
    {cue: "correlate", service: "twin", view: "service_dependency_path",
      itil_practice: "service_configuration_management", owner_role: "noc_l2",
      handoff: "noc_l1_to_noc_l2", evidence_required: "ci_edge_source_and_freshness",
      status: "MISSING"},
    {cue: "ticket", service: "glpi", view: "incident_ticket",
      itil_practice: "incident_management", owner_role: "service_desk_n1",
      handoff: "noc_l2_to_service_desk", evidence_required: "ticket_source_and_tenant",
      status: "MISSING"}
  ];
  return {
    schema: "aiops.acme-explore-story.v1", mode, action, cursor,
    playing: mode === "story" && action !== "pause" && cursor < timeline.length - 1,
    provenance: "SIMULATED_TARGET", source_sha256: "a".repeat(64),
    scenario: {run_id: "SIM-ACME-TEST", incident_id: "ACME-DEMO-SAN-001",
      impact_incident_id: "ACME-DEMO-PAY-002",
      impact_path: ["SAN-FABRIC-A", "HOST-ESX-01", "VM-PAY-01", "APP-PAY-01"],
      ticket_id: null, event_timestamp_utc: null},
    timeline, step: timeline[cursor], runtime_attested: false,
    production_qualified: false, live_remediation_authorized: false,
    ...overrides
  };
}

test("anonymous controls do not fetch; authenticated Explore renders without cookies or storage", async () => {
  const h = harness(async (_, opts) => {
    const p = JSON.parse(opts.body);
    return {ok: true, json: async () => envelope(p.action, p.mode, p.cursor)};
  });
  await h.get("start").click();
  assert.equal(h.requests.length, 0);
  assert.match(h.get("story-status").textContent, /UNKNOWN/);
  h.get("story-token").value = "synthetic-viewer";
  await h.get("start").click();
  assert.equal(h.requests.length, 1);
  assert.equal(h.requests[0].options.credentials, "omit");
  assert.equal(h.requests[0].options.cache, "no-store");
  assert.equal(h.requests[0].options.redirect, "error");
  assert.equal(h.get("story-token").value, "");
  assert.equal(h.get("timeline").children.length, 3);
  assert.match(h.get("scenario").textContent, /SAN-FABRIC-A/);
  assert.match(h.get("step-detail").textContent, /monitoring_event_management/);
  assert.match(h.get("step-detail").textContent, /monitoring_to_noc_l1/);
  assert.equal(h.timer(), null);
});

test("Story starts, pauses and clears in-memory credentials", async () => {
  const h = harness(async (_, opts) => {
    const p = JSON.parse(opts.body);
    return {ok: true, json: async () => envelope(p.action, p.mode, p.cursor)};
  });
  h.get("mode-story").click();
  h.get("story-token").value = "viewer-only";
  await h.get("start").click();
  assert.equal(typeof h.timer(), "function");
  await h.get("pause").click();
  assert.equal(h.timer(), null);
  h.get("clear").click();
  assert.match(h.get("story-status").textContent, /UNKNOWN/);
  await h.get("advance").click();
  assert.equal(h.requests.length, 2);
});

test("false LIVE attestation is rejected and late responses cannot resurrect cleared view", async () => {
  const h = harness(async (_, opts) => {
    const p = JSON.parse(opts.body);
    return {ok: true, json: async () => envelope(p.action, p.mode, p.cursor,
      {runtime_attested: true})};
  });
  h.get("story-token").value = "viewer";
  await h.get("start").click();
  assert.match(h.get("story-status").textContent, /UNKNOWN/);
  assert.equal(h.get("timeline").children.length, 1);

  let finish;
  const late = harness(() => new Promise(resolve => { finish = resolve; }));
  late.get("story-token").value = "viewer";
  const pending = late.get("start").click();
  await flush();
  late.get("clear").click();
  finish({ok: true, json: async () => envelope("start", "explore", 0)});
  await pending;
  assert.match(late.get("story-status").textContent, /UNKNOWN/);
  assert.equal(late.get("timeline").children.length, 1);
});

test("control responses cannot skip checkpoints or forge playing state", async () => {
  let forged = null;
  const h = harness(async (_, opts) => {
    const p = JSON.parse(opts.body);
    const expected = p.action === "advance" ? Math.min(p.cursor + 1, 2) : p.cursor;
    return {ok: true, json: async () => envelope(p.action, p.mode, expected, forged || {})};
  });
  h.get("story-token").value = "viewer";
  await h.get("start").click();
  assert.match(h.get("story-status").textContent, /SIMULATED_TARGET/);
  forged = {cursor: 2, step: envelope("advance", "explore", 2).step};
  await h.get("advance").click();
  assert.match(h.get("story-status").textContent, /UNKNOWN/);
  assert.equal(h.get("timeline").children.length, 1);
  assert.equal(h.timer(), null);

  const replay = harness(async (_, opts) => {
    const p = JSON.parse(opts.body);
    return {ok: true, json: async () => envelope(p.action, p.mode, p.cursor,
      {playing: true})};
  });
  replay.get("story-token").value = "viewer";
  await replay.get("start").click();
  assert.match(replay.get("story-status").textContent, /UNKNOWN/);
  assert.equal(replay.timer(), null);
});

test("fixture identity drift fails closed until explicit session clear", async () => {
  let digest = "a".repeat(64);
  const h = harness(async (_, opts) => {
    const p = JSON.parse(opts.body);
    return {ok: true, json: async () => envelope(p.action, p.mode, p.cursor,
      {source_sha256: digest})};
  });
  h.get("story-token").value = "viewer";
  await h.get("start").click();
  assert.match(h.get("story-status").textContent, /SIMULATED_TARGET/);
  digest = "b".repeat(64);
  await h.get("pause").click();
  assert.match(h.get("story-status").textContent, /UNKNOWN/);
  assert.equal(h.get("timeline").children.length, 1);
  h.get("clear").click();
  h.get("story-token").value = "viewer";
  await h.get("start").click();
  assert.match(h.get("story-status").textContent, /SIMULATED_TARGET/);
  assert.match(h.get("source").textContent, /bbbbbbbb/);
});

test("valid Story auto-advance, pause and replay follow server cursor contract", async () => {
  const h = harness(async (_, opts) => {
    const p = JSON.parse(opts.body);
    const cursor = p.action === "reset" || p.action === "replay" ? 0 :
      p.action === "advance" ? Math.min(p.cursor + 1, 2) :
      p.action === "start" && p.cursor === 2 ? 0 : p.cursor;
    return {ok: true, json: async () => envelope(p.action, p.mode, cursor)};
  });
  h.get("mode-story").click();
  h.get("story-token").value = "viewer";
  await h.get("start").click();
  assert.equal(typeof h.timer(), "function");
  const advance = h.timer();
  advance();
  await flush();
  assert.match(h.get("story-status").textContent, /2\/3/);
  await h.get("pause").click();
  assert.equal(h.timer(), null);
  await h.get("replay").click();
  assert.match(h.get("story-status").textContent, /1\/3/);
  assert.equal(typeof h.timer(), "function");
});
