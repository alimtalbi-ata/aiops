/** DOM-contract tests only: no browser, no network, no service integration. */
import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import vm from "node:vm";

const source = readFileSync(new URL("../app/portal/portal_navigation_client.js", import.meta.url), "utf8");
const ids = ["thruk", "grafana", "n8n", "glpi", "checkmk"];
const envelope = () => ({
  schema: "aiops-single-portal-component-registry-v1",
  navigation_mode: "EXTERNAL_BROWSER_LINKS_ONLY_NO_PROXY",
  runtime_verified: false,
  live_remediation_authorized: false,
  items: ids.map(id => ({
    id, state: "UNKNOWN", runtime_authenticated: false, route_mounted: false,
    available_in_portal: false, external_link_state: id === "grafana" ? "CONFIGURED_UNVERIFIED" : "UNCONFIGURED",
    external_url: id === "grafana" ? "https://grafana.example.invalid/d/ops" : null
  }))
});

function fixture(fetchImpl) {
  function element(tag) {
    return {
      tag, children: [], textContent: "", value: "", appendChild(child) { this.children.push(child); },
      replaceChildren(...children) { this.children = children; }
    };
  }
  const token = element("input");
  const status = element("span");
  const list = element("ul");
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

function links(list) {
  return list.children.flatMap(li => li.children.filter(child => child.tag === "a"));
}

test("authorized navigation clears token, excludes cookies and labels links unverified", async () => {
  let captured;
  const f = fixture(async (path, options) => {
    captured = {path, options};
    return {ok: true, json: async () => envelope()};
  });
  f.token.value = "synthetic-ci-viewer-token";
  await f.context.loadPortalNavigation();
  assert.equal(f.token.value, "");
  assert.equal(captured.path, "/api/portal/components");
  assert.equal(captured.options.headers.Authorization, "Bearer synthetic-ci-viewer-token");
  assert.equal(captured.options.cache, "no-store");
  assert.equal(captured.options.credentials, "omit");
  assert.equal(captured.options.redirect, "error");
  assert.equal(links(f.list).length, 1);
  assert.equal(links(f.list)[0].href, "https://grafana.example.invalid/d/ops");
  assert.equal(links(f.list)[0].rel, "noopener noreferrer");
  assert.match(f.status.textContent, /aucune preuve LIVE/);
});

test("forged LIVE claim and script URL fail closed without a partial link", async () => {
  for (const mutate of [
    model => { model.items[0].state = "OK"; },
    model => { model.items[1].external_url = "javascript:alert(1)"; },
    model => { model.items.push({...model.items[1]}); },
    model => { model.runtime_verified = true; }
  ]) {
    const model = envelope();
    mutate(model);
    const f = fixture(async () => ({ok: true, json: async () => model}));
    f.token.value = "synthetic-ci-viewer-token";
    await f.context.loadPortalNavigation();
    assert.equal(links(f.list).length, 0);
    assert.equal(f.list.children.length, 1);
    assert.match(f.status.textContent, /^UNKNOWN/);
    assert.equal(f.token.value, "");
  }
});

test("clear invalidates a delayed successful response even when fetch ignores abort", async () => {
  let resolveFetch;
  const f = fixture(() => new Promise(resolve => { resolveFetch = resolve; }));
  f.token.value = "synthetic-ci-viewer-token";
  const pending = f.context.loadPortalNavigation();
  f.context.clearPortalNavigation();
  resolveFetch({ok: true, json: async () => envelope()});
  await pending;
  assert.equal(links(f.list).length, 0);
  assert.equal(f.token.value, "");
  assert.match(f.status.textContent, /UNKNOWN — liens effacés/);
});

test("HTTP error and malformed response remain UNKNOWN", async () => {
  for (const response of [
    {ok: false},
    {ok: true, json: async () => ({schema: "unexpected"})}
  ]) {
    const f = fixture(async () => response);
    f.token.value = "synthetic-ci-viewer-token";
    await f.context.loadPortalNavigation();
    assert.equal(links(f.list).length, 0);
    assert.match(f.status.textContent, /^UNKNOWN/);
  }
});
