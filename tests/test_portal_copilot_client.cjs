"use strict";
// External one-shot Copilot client contract; no browser/Core/provider I/O.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function makeHandler(fetchImpl) {
  const source = fs.readFileSync(path.join(__dirname, "../app/portal/portal_copilot_client.js"), "utf8");
  const elements = {
    "copilot-token": { value: "viewer-token" },
    "copilot-question": { value: "sensitive question" },
    "copilot-submit": { disabled: false, addEventListener: (event, fn) => { elements.handler = fn; } },
    "copilot-status": { textContent: "" },
  };
  const context = {
    document: { getElementById: id => elements[id] },
    fetch: fetchImpl,
    String,
    JSON,
  };
  vm.runInNewContext(source, context, { filename: "portal-copilot-client.js" });
  assert.equal(typeof elements.handler, "function", "Copilot click handler must be registered");
  return { ask: elements.handler, elements };
}

for (const code of [401, 403, 503]) {
  test("Copilot shows HTTP " + code + " without claiming a response", async () => {
    let seen = false;
    const { ask, elements } = makeHandler(async (url, options) => {
      seen = true;
      assert.equal(url, "/api/copilot");
      assert.equal(options.method, "POST");
      assert.equal(options.credentials, "omit");
      assert.equal(options.cache, "no-store");
      assert.equal(options.redirect, "error");
      assert.equal(JSON.parse(options.body).question, "sensitive question");
      assert.equal(options.headers.Authorization, "Bearer viewer-token");
      assert.equal(elements["copilot-token"].value, "");
      return { status: code, ok: false, json: async () => ({ reason: "TENANT_ACL_NOT_QUALIFIED" }) };
    });
    await ask();
    assert.equal(seen, true);
    assert.match(elements["copilot-status"].textContent, new RegExp("HTTP " + code));
    assert.match(elements["copilot-status"].textContent, /UNAUTHORIZED|UNKNOWN/);
    assert.doesNotMatch(elements["copilot-status"].textContent, /success|approved|verified/i);
  });
}

test("Copilot transport error remains UNKNOWN", async () => {
  const { ask, elements } = makeHandler(async () => { throw new Error("upstream secret"); });
  await ask();
  assert.match(elements["copilot-status"].textContent, /Copilot indisponible/);
  assert.doesNotMatch(elements["copilot-status"].textContent, /upstream secret/);
});
