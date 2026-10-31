/* Portal bootstrap read UI. No token persistence, no HTML interpolation. */
(() => {
  "use strict";
  let generation = 0;
  const $ = (id) => document.getElementById(id);
  const metricKeys = ["open_p1", "open_incidents", "running", "blocked", "twin_nodes", "degraded_nodes"];
  function clear() {
    generation += 1;
    if ($("portal-read-token")) $("portal-read-token").value = "";
    for (const key of metricKeys) {
      const node = document.querySelector('[data-metric="' + key + '"]');
      if (node) node.textContent = "UNKNOWN";
    }
    const rows = $("portal-runs");
    if (rows) {
      rows.replaceChildren();
      const tr = document.createElement("tr");
      const td = document.createElement("td");
      td.colSpan = 5;
      td.textContent = "UNKNOWN — lecture non attestée";
      tr.appendChild(td);
      rows.appendChild(tr);
    }
    if ($("portal-twin")) $("portal-twin").textContent = "UNKNOWN";
    if ($("portal-states")) $("portal-states").textContent = "UNKNOWN";
    if ($("portal-read-result")) $("portal-read-result").textContent = "UNKNOWN — accès non authentifié";
  }
  // Reject forged or contradictory envelopes before touching any UI element.
  // The server's READABLE_UNVERIFIED is never proof of runtime attestation.
  function validEnvelope(data) {
    if (!data || typeof data !== "object" || Array.isArray(data) ||
        data.schema !== "aiops.portal.readmodels.v1" ||
        data.provenance !== "UNATTESTED_UPSTREAM_API_READ" ||
        data.runtime_authenticated !== false ||
        data.live_remediation_authorized !== false) return false;
    const states = data.states;
    if (!states || typeof states !== "object" || Array.isArray(states)) return false;
    for (const key of ["dashboard", "runs", "twin"]) {
      if (!["UNKNOWN", "READABLE_UNVERIFIED"].includes(states[key])) return false;
      if (states[key] === "UNKNOWN" && data[key] !== null) return false;
      if (states[key] === "READABLE_UNVERIFIED" &&
          (!data[key] || typeof data[key] !== "object" || Array.isArray(data[key]))) return false;
    }
    if (states.dashboard === "READABLE_UNVERIFIED" &&
        !metricKeys.every((key) => Number.isSafeInteger(data.dashboard[key]) &&
                                    data.dashboard[key] >= 0)) return false;
    if (states.runs === "READABLE_UNVERIFIED" &&
        (!Array.isArray(data.runs.items) || data.runs.items.length > 100 ||
         !data.runs.items.every((run) => run && typeof run === "object" &&
           !Array.isArray(run) && typeof run.run_id === "string" && run.run_id.length > 0))) return false;
    if (states.twin === "READABLE_UNVERIFIED" &&
        !["nodes", "edges"].every((key) => Number.isSafeInteger(data.twin[key]) &&
                                         data.twin[key] >= 0)) return false;
    return true;
  }
  function show(data) {
    if (!validEnvelope(data)) return false;
    const states = data.states;
    for (const [index, key] of metricKeys.entries()) {
      const node = document.querySelector('[data-metric="' + key + '"]');
      const value = data.dashboard && data.dashboard[key];
      if (node) node.textContent = states.dashboard === "READABLE_UNVERIFIED" &&
        Number.isSafeInteger(value) && value >= 0 ? String(value) : "UNKNOWN";
    }
    const rows = $("portal-runs");
    if (rows && states.runs === "READABLE_UNVERIFIED" && data.runs &&
        Array.isArray(data.runs.items)) {
      rows.replaceChildren();
      for (const run of data.runs.items.slice(0, 15)) {
        if (!run || typeof run.run_id !== "string") continue;
        const tr = document.createElement("tr");
        for (const field of ["run_id", "mode", "status", "overall_confidence", "scenario_id"]) {
          const td = document.createElement("td");
          td.textContent = String(run[field] ?? "UNKNOWN").slice(0, 256);
          tr.appendChild(td);
        }
        rows.appendChild(tr);
      }
      if (!rows.children.length) {
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = 5;
        td.textContent = "Aucun Run dans la réponse non attestée";
        tr.appendChild(td);
        rows.appendChild(tr);
      }
    }
    if ($("portal-twin") && states.twin === "READABLE_UNVERIFIED" &&
        data.twin && Number.isSafeInteger(data.twin.nodes) &&
        Number.isSafeInteger(data.twin.edges)) {
      $("portal-twin").textContent = JSON.stringify({
        nodes: data.twin.nodes, edges: data.twin.edges
      }, null, 2);
    }
    if ($("portal-states")) $("portal-states").textContent =
      ["dashboard", "runs", "twin"].map((key) => key + ": " + states[key]).join(" | ");
    return true;
  }
  async function load() {
    const input = $("portal-read-token");
    const token = input ? input.value : "";
    if (input) input.value = "";
    clear();
    const current = generation;
    if (!token) return;
    if ($("portal-read-result")) $("portal-read-result").textContent = "UNKNOWN — lecture en cours";
    try {
      const response = await fetch("/api/portal/bootstrap", {
        headers: {Authorization: "Bearer " + token},
        cache: "no-store", credentials: "omit", redirect: "error"
      });
      if (current !== generation) return;
      if (!response.ok) {
        if ($("portal-read-result")) $("portal-read-result").textContent =
          response.status === 401 || response.status === 403
            ? "UNAUTHORIZED (HTTP " + response.status + ") — lecture refusée"
            : response.status === 503
              ? "UNKNOWN (HTTP 503) — autorisation tenant non qualifiée ou source indisponible"
              : "UNKNOWN (HTTP " + response.status + ") — lecture non qualifiée";
        return;
      }
      const data = await response.json();
      if (current !== generation) return;
      if (!show(data)) {
        if ($("portal-read-result")) $("portal-read-result").textContent =
          "UNKNOWN — contrat de lecture invalide";
        return;
      }
      if ($("portal-read-result")) $("portal-read-result").textContent =
        Object.values(data.states).includes("READABLE_UNVERIFIED") ?
          "READABLE_UNVERIFIED — aucune attestation LIVE" :
          "UNKNOWN — aucune source lisible";
    } catch (_) {
      if (current === generation && $("portal-read-result"))
        $("portal-read-result").textContent = "UNKNOWN — service indisponible";
    }
  }
  window.loadPortalReadModel = load;
  window.clearPortalReadModel = clear;
})();
