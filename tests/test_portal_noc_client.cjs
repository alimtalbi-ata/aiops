"use strict";
// Synthetic DOM-only tests for Portal's inline NOC handlers; no Core/GLPI network.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

function makeNocHandlers(fetchImpl, token = "one-time-viewer-token") {
  const python = fs.readFileSync(path.join(__dirname, "../app/portal/main.py"), "utf8");
  const start = python.indexOf("function portalNocStatus(r){{");
  const end = python.indexOf("</script>", start);
  assert.ok(start >= 0 && end > start, "NOC inline handlers must exist");
  const source = python.slice(start, end).replaceAll("{{", "{").replaceAll("}}", "}");
  const elements = {
    "noc-token": { value: token },
    "noc-result": { textContent: "" },
    "noc-grafana-result": { textContent: "" },
    "noc-rag-result": { textContent: "" },
    "noc-asset": { value: "brocade-fc01" },
  };
  const context = {
    document: { getElementById: id => elements[id] },
    fetch: fetchImpl,
    JSON, String, encodeURIComponent,
  };
  vm.runInNewContext(source, context, { filename: "portal-noc-inline.js" });
  for (const name of ["correlateNoc", "grafanaHealth", "demoRag"]) {
    assert.equal(typeof context[name], "function");
  }
  return { handlers: context, elements };
}

const routes = [
  ["correlateNoc", "/api/noc/correlation", "noc-result"],
  ["grafanaHealth", "/api/noc/grafana-health", "noc-grafana-result"],
  ["demoRag", "/api/noc/demo-rag?asset=brocade-fc01", "noc-rag-result"],
];

for (const [handler, route, resultId] of routes) {
  for (const status of [401, 403, 503]) {
    test(handler + " preserves HTTP " + status + " and redacts upstream errors", async () => {
      let calls = 0;
      const { handlers, elements } = makeNocHandlers(async (url, options) => {
        calls++;
        assert.equal(url, route);
        assert.equal(options.headers.Authorization, "Bearer one-time-viewer-token");
        assert.equal(options.credentials, "omit");
        assert.equal(options.cache, "no-store");
        assert.equal(options.redirect, "error");
        assert.equal(elements["noc-token"].value, "", "token cleared before fetch");
        return {
          ok: false, status,
          json: async () => ({ detail: "private-upstream-host-secret", reason: "TENANT_ACL_NOT_QUALIFIED" }),
        };
      });
      await handlers[handler]();
      assert.equal(calls, 1);
      assert.equal(elements["noc-token"].value, "");
      assert.match(elements[resultId].textContent, new RegExp("HTTP " + status));
      assert.match(elements[resultId].textContent, /UNAUTHORIZED|UNKNOWN/);
      assert.doesNotMatch(elements[resultId].textContent, /private-upstream-host-secret|CONNECTED/);
    });
  }
}

for (const [handler, , resultId] of routes.slice(0, 2)) {
  test(handler + " rejects HTTP 200 without server-qualified tenant ACL", async () => {
    const { handlers, elements } = makeNocHandlers(async () => ({
      ok: true, status: 200,
      json: async () => ({ state: "CONNECTED", tenant_acl_qualified: false,
                            ticket_id: "SECRET-CROSS-TENANT" }),
    }));
    await handlers[handler]();
    assert.match(elements[resultId].textContent, /UNKNOWN \(HTTP 200\)/);
    assert.doesNotMatch(elements[resultId].textContent, /CONNECTED|SECRET-CROSS-TENANT/);
  });
}

test("synthetic RAG stays visibly SYNTHETIC, never runtime-attested", async () => {
  const { handlers, elements } = makeNocHandlers(async () => ({
    ok: true, status: 200,
    json: async () => ({ state: "SYNTHETIC_REFERENCE_ONLY",
                          data_classification: "SYNTHETIC_SIMULATION_ONLY",
                          tenant_acl_qualified: false, source_runtime_observed: false,
                          runtime_authenticated: false, live_remediation_authorized: false,
                          citations: [] }),
  }));
  await handlers.demoRag();
  assert.match(elements["noc-rag-result"].textContent, /^SYNTHETIC — /);
  assert.doesNotMatch(elements["noc-rag-result"].textContent, /CONNECTED/);
});

test("RAG rejects forged 200 runtime-attested data", async () => {
  const { handlers, elements } = makeNocHandlers(async () => ({
    ok: true, status: 200,
    json: async () => ({ state: "CONNECTED", data_classification: "SYNTHETIC_SIMULATION_ONLY",
                          tenant_acl_qualified: false, source_runtime_observed: false,
                          runtime_authenticated: false, live_remediation_authorized: false,
                          ticket_id: "SECRET" }),
  }));
  await handlers.demoRag();
  assert.match(elements["noc-rag-result"].textContent, /UNKNOWN \(HTTP 200\)/);
  assert.doesNotMatch(elements["noc-rag-result"].textContent, /CONNECTED|SECRET/);
});

// A late response from an older click must never replace a newer refusal.
for (const [handler, , resultId] of routes) {
  test(handler + " ignores stale HTTP 200 after a newer HTTP 403", async () => {
    let release;
    const delayedJson = new Promise(resolve => { release = resolve; });
    let calls = 0;
    const { handlers, elements } = makeNocHandlers(async () => {
      if (++calls === 1) return { ok: true, status: 200, json: () => delayedJson };
      return { ok: false, status: 403, json: async () => ({ reason: "forbidden" }) };
    });
    const first = handlers[handler]();
    elements["noc-token"].value = "second-operator-token";
    await handlers[handler]();
    assert.equal(calls, 2);
    assert.match(elements[resultId].textContent, /HTTP 403/);
    release(handler === "demoRag"
      ? { state: "SYNTHETIC_REFERENCE_ONLY",
          data_classification: "SYNTHETIC_SIMULATION_ONLY",
          tenant_acl_qualified: false, source_runtime_observed: false,
          runtime_authenticated: false, live_remediation_authorized: false,
          citations: [{ doc_id: "STALE_PRIVATE_CITATION" }] }
      : { state: "CONNECTED", tenant_acl_qualified: true, ticket_id: "STALE_PRIVATE_TICKET" });
    await first;
    assert.match(elements[resultId].textContent, /HTTP 403/);
    assert.doesNotMatch(elements[resultId].textContent, /STALE_PRIVATE|CONNECTED|SYNTHETIC —/);
  });

  test(handler + " ignores stale network errors after a newer refusal", async () => {
    let rejectOld;
    const pending = new Promise((_, reject) => { rejectOld = reject; });
    let calls = 0;
    const { handlers, elements } = makeNocHandlers(async () => {
      if (++calls === 1) return pending;
      return { ok: false, status: 401, json: async () => ({ reason: "unauthorized" }) };
    });
    const first = handlers[handler]();
    elements["noc-token"].value = "second-operator-token";
    await handlers[handler]();
    rejectOld(Error("STALE_PRIVATE_UPSTREAM"));
    await first;
    assert.match(elements[resultId].textContent, /HTTP 401/);
    assert.doesNotMatch(elements[resultId].textContent, /STALE_PRIVATE|indisponible/);
  });
}

test("a missing token on the latest click invalidates an in-flight NOC response", async () => {
  let release;
  const pending = new Promise(resolve => { release = resolve; });
  const { handlers, elements } = makeNocHandlers(async () => ({
    ok: true, status: 200, json: () => pending
  }));
  const first = handlers.correlateNoc();
  elements["noc-token"].value = "";
  await handlers.correlateNoc();
  release({ state: "CONNECTED", tenant_acl_qualified: true, ticket_id: "STALE_PRIVATE" });
  await first;
  assert.match(elements["noc-result"].textContent, /jeton opérateur requis/);
  assert.doesNotMatch(elements["noc-result"].textContent, /CONNECTED|STALE_PRIVATE/);
});

test("missing token never triggers NOC request", async () => {
  const { handlers, elements } = makeNocHandlers(async () => {
    throw Error("unexpected upstream");
  }, "");
  await handlers.correlateNoc();
  assert.match(elements["noc-result"].textContent, /UNKNOWN/);
});

test("transport errors are redacted", async () => {
  const { handlers, elements } = makeNocHandlers(async () => {
    throw Error("private-upstream-host-secret");
  });
  await handlers.grafanaHealth();
  assert.match(elements["noc-grafana-result"].textContent, /UNKNOWN/);
  assert.doesNotMatch(elements["noc-grafana-result"].textContent, /private-upstream-host-secret/);
});
