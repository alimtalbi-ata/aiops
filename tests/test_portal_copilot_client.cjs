"use strict";
// Synthetic DOM contract for the existing inline Copilot handler; no browser/Core.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function makeHandler(fetchImpl) {
  const python = fs.readFileSync(path.join(__dirname, "../app/portal/main.py"), "utf8");
  const start = python.indexOf("async function ask(){{");
  const end = python.indexOf("async function correlateNoc(){{", start);
  assert.ok(start >= 0 && end > start, "Copilot inline handler must be present");
  const source = python.slice(start, end).replaceAll("{{", "{").replaceAll("}}", "}");
  const elements = { q: { value: "sensitive question" }, a: { textContent: "" } };
  const context = {
    document: { getElementById: id => elements[id] },
    fetch: fetchImpl,
    String,
    JSON,
  };
  vm.runInNewContext(source, context, { filename: "portal-copilot-inline.js" });
  assert.equal(typeof context.ask, "function");
  return { ask: context.ask, elements };
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
      assert.equal(options.headers.Authorization, undefined);
      return { status: code, json: async () => ({ reason: "TENANT_ACL_NOT_QUALIFIED" }) };
    });
    await ask();
    assert.equal(seen, true);
    assert.match(elements.a.textContent, new RegExp("HTTP " + code));
    assert.match(elements.a.textContent, /UNAUTHORIZED|UNKNOWN/);
    assert.doesNotMatch(elements.a.textContent, /success|approved|verified/i);
  });
}

test("Copilot transport error remains UNKNOWN", async () => {
  const { ask, elements } = makeHandler(async () => { throw new Error("upstream secret"); });
  await ask();
  assert.match(elements.a.textContent, /UNKNOWN/);
  assert.doesNotMatch(elements.a.textContent, /upstream secret/);
});
