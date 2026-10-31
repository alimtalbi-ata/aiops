/* Explicit read-only navigation. No persisted token, no LIVE attestation. */
"use strict";
let portalNavEpoch = 0;
let portalNavAbort = null;
const PORTAL_NAV_IDS = ["thruk", "grafana", "n8n", "glpi", "checkmk"];

function privateNavigationHost(host) {
  const h = host.replace(/^\[|\]$/g, "").toLowerCase();
  if (h.includes(":")) return /^(fc|fd)[0-9a-f]{2}:/.test(h);
  const p = h.split(".");
  if (p.length !== 4 || p.some(x => !/^(0|[1-9][0-9]{0,2})$/.test(x) || Number(x) > 255)) return false;
  const n = p.map(Number);
  return n[0] === 10 || (n[0] === 172 && n[1] >= 16 && n[1] <= 31) ||
         (n[0] === 192 && n[1] === 168);
}
function safeNavigationUrl(raw) {
  if (typeof raw !== "string" || raw.length > 2048 || /[\s\\\u0000-\u001f\u007f]/.test(raw)) return null;
  try {
    const u = new URL(raw);
    if (!["https:", "http:"].includes(u.protocol) || !u.hostname || u.username || u.password ||
        u.search || u.hash || (u.protocol === "http:" && !privateNavigationHost(u.hostname))) return null;
    return u.href;
  } catch (_) { return null; }
}
function resetPortalNavigation(message) {
  const list = document.querySelector("#integrations ul");
  if (list) {
    const li = document.createElement("li");
    li.textContent = "UNKNOWN — liens non chargés";
    list.replaceChildren(li);
  }
  document.getElementById("portal-navigation-status").textContent = message;
}
function clearPortalNavigation() {
  portalNavEpoch++;
  if (portalNavAbort) portalNavAbort.abort();
  portalNavAbort = null;
  document.getElementById("portal-navigation-token").value = "";
  resetPortalNavigation("UNKNOWN — liens effacés");
}
async function loadPortalNavigation() {
  const input = document.getElementById("portal-navigation-token");
  const token = input.value;
  input.value = "";
  const epoch = ++portalNavEpoch;
  if (portalNavAbort) portalNavAbort.abort();
  portalNavAbort = null;
  resetPortalNavigation("UNKNOWN — chargement");
  if (!token) { resetPortalNavigation("UNKNOWN — jeton requis"); return; }
  const controller = new AbortController();
  portalNavAbort = controller;
  try {
    const response = await fetch("/api/portal/components", {
      headers: {Authorization: "Bearer " + token}, cache: "no-store",
      redirect: "error", credentials: "omit", signal: controller.signal
    });
    if (epoch !== portalNavEpoch) return;
    if (!response.ok) { resetPortalNavigation("UNKNOWN — accès refusé"); return; }
    const model = await response.json();
    if (epoch !== portalNavEpoch) return;
    // A legacy HTTP 200 registry is not an actor/tenant-scoped authorization.
    // These claims must originate from a future server-authorized contract;
    // the current Portal route intentionally never issues them.
    if (!model || model.tenant_acl_qualified !== true ||
        model.actor_identity_server_derived !== true ||
        model.schema !== "aiops-single-portal-component-registry-v1" ||
        model.navigation_mode !== "EXTERNAL_BROWSER_LINKS_ONLY_NO_PROXY" ||
        model.runtime_verified !== false || model.live_remediation_authorized !== false ||
        !Array.isArray(model.items)) throw Error("invalid envelope");
    const rows = [];
    for (const id of PORTAL_NAV_IDS) {
      const matches = model.items.filter(item => item && item.id === id);
      if (matches.length !== 1) throw Error("missing or duplicate integration");
      const item = matches[0];
      if (item.state !== "UNKNOWN" || item.runtime_authenticated !== false ||
          item.route_mounted !== false || item.available_in_portal !== false ||
          !["CONFIGURED_UNVERIFIED", "UNCONFIGURED", "REJECTED_CONFIGURATION"].includes(item.external_link_state))
        throw Error("invalid state");
      const url = item.external_url === null ? null : safeNavigationUrl(item.external_url);
      if ((item.external_link_state === "CONFIGURED_UNVERIFIED") !== Boolean(url))
        throw Error("invalid URL");
      rows.push({id, url, state: item.external_link_state});
    }
    const list = document.querySelector("#integrations ul");
    if (!list) throw Error("navigation missing");
    const elements = rows.map(row => {
      const li = document.createElement("li");
      if (row.url) {
        const a = document.createElement("a");
        a.href = row.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.referrerPolicy = "no-referrer";
        a.textContent = row.id;
        li.appendChild(a);
      } else {
        li.textContent = row.id;
      }
      li.appendChild(document.createTextNode(" — " + row.state + " / UNKNOWN"));
      return li;
    });
    if (epoch !== portalNavEpoch) return;
    list.replaceChildren(...elements);
    document.getElementById("portal-navigation-status").textContent = "CONFIGURED_UNVERIFIED — aucune preuve LIVE";
  } catch (_) {
    if (epoch === portalNavEpoch) resetPortalNavigation("UNKNOWN — réponse refusée");
  } finally {
    if (epoch === portalNavEpoch) portalNavAbort = null;
  }
}
