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
    {cue: "detect", service: "grafana", view: "alert_dashboard", status: "MISSING"},
    {cue: "correlate", service: "n8n", view: "ingress_execution", status: "MISSING"},
    {cue: "ticket", service: "glpi", view: "incident_ticket", status: "MISSING"}
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
  const h = harness(async (_, opts) => ({
    ok: true, json: async () => envelope(...Object.values(JSON.parse(opts.body)).slice(0, 0),
      JSON.parse(opts.body).mode, JSON.parse(opts.body).cursor,
      {action: JSON.parse(opts.body).action})
  }));
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
