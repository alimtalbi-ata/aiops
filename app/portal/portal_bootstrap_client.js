/* Portal bootstrap read UI. No token persistence, no HTML interpolation. */
(() => {
  "use strict";
  let generation = 0;
  const $ = (id) => document.getElementById(id);
  const metricKeys = ["open_p1", "open_incidents", "running", "blocked", "twin_nodes", "degraded_nodes"];
  function clear() {
    generation += 1;
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
  function show(data) {
    const states = data && data.states;
    if (!states || typeof states !== "object") return;
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
      ["dashboard", "runs", "twin"].map((key) =>
        key + ": " + (["UNKNOWN", "READABLE_UNVERIFIED"].includes(states[key]) ?
          states[key] : "UNKNOWN")).join(" | ");
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
          "UNKNOWN — accès refusé ou source indisponible";
        return;
      }
      const data = await response.json();
      if (current !== generation) return;
      show(data);
      if ($("portal-read-result")) $("portal-read-result").textContent =
        "READABLE_UNVERIFIED — aucune attestation LIVE";
    } catch (_) {
      if (current === generation && $("portal-read-result"))
        $("portal-read-result").textContent = "UNKNOWN — service indisponible";
    }
  }
  window.loadPortalReadModel = load;
  window.clearPortalReadModel = clear;
})();
