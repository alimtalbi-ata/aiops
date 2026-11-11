/** Read-only DOM regression: superseded navigation responses must never restore links.
 * Synthetic server-qualified envelopes only; no tenant ACL is enabled by this test.
 * Run: node --test tests/test_portal_navigation_supersession.mjs
 */
import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../app/portal/portal_navigation_client.js", import.meta.url), "utf8");
const ids = ["thruk", "grafana", "n8n", "glpi", "checkmk"];
function model(url) {
  return {
    schema: "aiops-single-portal-component-registry-v1",
    navigation_mode: "EXTERNAL_BROWSER_LINKS_ONLY_NO_PROXY",
    tenant_acl_qualified: true, actor_identity_server_derived: true,
    runtime_verified: false, live_remediation_authorized: false,
    items: ids.map(id => ({
      id, state: "UNKNOWN", runtime_authenticated: false,
      route_mounted: false, available_in_portal: false,
      external_link_state: id === "grafana" ? "CONFIGURED_UNVERIFIED" : "UNCONFIGURED",
      external_url: id === "grafana" ? url : null
    }))
  };
}
function deferred() {
  let resolve;
  const promise = new Promise(r => { resolve = r; });
  return {promise, resolve};
}
function fixture(fetchImpl) {
  const element = tag => ({
    tag, children: [], textContent: "", value: "",
    appendChild(child) { this.children.push(child); },
    replaceChildren(...children) { this.children = children; }
  });
  const token = element("input"), status = element("span"), list = element("ul");
  const document = {
    getElementById(id) {
      return {"portal-navigation-token": token, "portal-navigation-status": status}[id] ?? null;
    },
    querySelector(selector) { return selector === "#integrations ul" ? list : null; },
    createElement: element,
    createTextNode(text) { return {tag: "text", textContent: text}; }
  };
  const context = vm.createContext({document, fetch: fetchImpl, URL, AbortController});
  vm.runInContext(source, context, {filename: "portal_navigation_client.js"});
  return {context, token, status, list};
}
const urls = list => list.children.flatMap(li => li.children.filter(x => x.tag === "a").map(x => x.href));

test("superseded fetch cannot replace newer navigation, even if abort is ignored", async () => {
  const old = deferred(), newer = deferred(), requests = [];
  const f = fixture((path, options) => {
    requests.push({path, options});
    return requests.length === 1 ? old.promise : newer.promise;
  });
  f.token.value = "synthetic-old";
  const first = f.context.loadPortalNavigation();
  f.token.value = "synthetic-new";
  const second = f.context.loadPortalNavigation();
  assert.equal(requests.length, 2);
  assert.equal(requests[0].options.signal.aborted, true);
  assert.equal(requests[1].options.signal.aborted, false);
  newer.resolve({ok: true, json: async () => model("https://new.example.invalid/ops")});
  await second;
  old.resolve({ok: true, json: async () => model("https://old.example.invalid/ops")});
  await first;
  assert.deepEqual(urls(f.list), ["https://new.example.invalid/ops"]);
  assert.equal(f.token.value, "");
  assert.match(f.status.textContent, /CONFIGURED_UNVERIFIED/);
});

test("superseded JSON parsing cannot replace newer navigation", async () => {
  const oldJson = deferred();
  let calls = 0;
  const f = fixture(async () => {
    calls++;
    if (calls === 1) return {ok: true, json: () => oldJson.promise};
    return {ok: true, json: async () => model("https://new.example.invalid/ops")};
  });
  f.token.value = "synthetic-old";
  const first = f.context.loadPortalNavigation();
  // Let the first fetch resolve and enter its delayed JSON parser.
  await Promise.resolve();
  await Promise.resolve();
  f.token.value = "synthetic-new";
  await f.context.loadPortalNavigation();
  oldJson.resolve(model("https://old.example.invalid/ops"));
  await first;
  assert.deepEqual(urls(f.list), ["https://new.example.invalid/ops"]);
  assert.match(f.status.textContent, /CONFIGURED_UNVERIFIED/);
});
