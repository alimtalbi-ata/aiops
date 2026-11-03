/* P0 #385: read-only NOC; never turn a signed source into actor/tenant ALLOW. */
"use strict";
(() => {
  const byId = id => document.getElementById(id);
  let epoch = 0, controller = null, rows = [];
  function showUnknown(message) {
    rows = [];
    byId("noc-state").textContent = message;
    byId("noc-correlation").textContent = "Corrélation Core : NOT_ATTESTED";
    render();
  }
  function render() {
    const body = byId("noc-rows");
    body.replaceChildren();
    const filter = byId("noc-filter").value;
    const selected = rows.filter(r => filter === "ALL" || r.state === filter);
    if (!selected.length) {
      const tr = document.createElement("tr"), td = document.createElement("td");
      td.colSpan = 4;
      td.textContent = rows.length ? "Aucun incident pour ce filtre" : "UNKNOWN — aucun incident autorisé";
      tr.appendChild(td); body.appendChild(tr); return;
    }
    for (const row of selected) {
      const tr = document.createElement("tr");
      for (const value of [row.id, row.state, row.provenance, row.evidence]) {
        const td = document.createElement("td"); td.textContent = value; tr.appendChild(td);
      }
      body.appendChild(tr);
    }
  }
  function cancel() {
    ++epoch;
    if (controller) controller.abort();
    controller = null;
    byId("noc-viewer-token").value = "";
  }
  byId("noc-clear").addEventListener("click", () => {
    cancel(); showUnknown("UNKNOWN — lecture effacée");
    byId("noc-diagnostic").textContent = "NOC : NOT_VERIFIED · n8n login : NOT_VERIFIED · GLPI humain : NOT_VERIFIED";
  });
  byId("noc-filter").addEventListener("change", render);
  byId("noc-load").addEventListener("click", async () => {
    const token = byId("noc-viewer-token").value;
    cancel();
    const current = epoch;
    showUnknown("UNKNOWN — vérification en cours");
    if (!token) { showUnknown("UNKNOWN — jeton de lecture requis"); return; }
    controller = new AbortController();
    try {
      const response = await fetch("/api/noc/runtime-state", {
        headers: {Authorization: "Bearer " + token},
        credentials: "omit", cache: "no-store", redirect: "error", signal: controller.signal
      });
      if (current !== epoch) return;
      if (!response.ok) {
        const reason = response.status === 401 ? "AUTHENTICATION_REQUIRED" :
                       response.status === 403 ? "FORBIDDEN" :
                       response.status === 503 ? "AUTHORITY_UNAVAILABLE" : "UPSTREAM_UNVERIFIED";
        showUnknown("UNKNOWN / " + response.status + " — " + reason);
        byId("noc-diagnostic").textContent = "NOC : " + reason + " · aucune donnée promue";
        return;
      }
      const data = await response.json();
      if (current !== epoch) return;
      // Existing portal routes deliberately return 503 until actor+tenant ACL is qualified.
      // Even a future 200 must carry independently verified actor/tenant flags.
      if (!data || data.tenant_acl_qualified !== true ||
          data.actor_identity_server_derived !== true ||
          data.schema !== "aiops.noc-runtime-envelope.v1" ||
          data.source_payload_authenticated !== true ||
          data.runtime_authenticated !== false ||
          data.live_remediation_authorized !== false ||
          typeof data.incident_id !== "string" || typeof data.run_id !== "string" ||
          !/^[A-Za-z0-9][A-Za-z0-9_.-]{1,95}$/.test(data.incident_id) ||
          !/^[A-Za-z0-9][A-Za-z0-9_.-]{1,95}$/.test(data.run_id))
        throw Error("UNQUALIFIED_NOC_ENVELOPE");
      rows = [{
        id: data.incident_id + " / " + data.run_id,
        state: "UNKNOWN",
        provenance: "SIGNED_SOURCE_ONLY",
        evidence: "NOT_ATTESTED — ouvrir Core après ACL"
      }];
      byId("noc-state").textContent = "SOURCE_SIGNED — état métier UNKNOWN";
      byId("noc-diagnostic").textContent = "NOC : SIGNED_SOURCE_ONLY · impact SAN/ERP NOT_ATTESTED";
      render();
    } catch (_) {
      if (current === epoch) showUnknown("UNKNOWN — réponse non qualifiée ou indisponible");
    } finally {
      if (current === epoch) controller = null;
    }
  });
})();
