"use strict";
// Only the ACME-TEST synthetic Core ticket readback. Never native GLPI READ/READMY.
(() => {
  const el = id => document.getElementById(id);
  const read = el("sim-read"), clear = el("sim-clear");
  if (!read || !clear) return;
  let epoch = 0;
  const attemptPattern = /^ACME-SIM-[A-Z0-9_-]{8,80}$/;
  const idPattern = /^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$/;
  // The server projects a closed, simulation-only schema. A forged 200 must
  // not smuggle human IdP/GLPI/ACL/LIVE claims into the browser readback.
  const readbackKeys = [
    "schema", "authority", "ticket_authority", "state", "simulated",
    "tenant_id", "attempt_id", "scenario_id", "mode", "ticket",
    "incident_id", "run_id", "worker_receipt_status", "worker_receipt_phase",
    "worker_no_effect_verified", "core_resolution_after_worker_verified",
    "terminal_ticket_digest_verified", "independent_final_read_rounds",
    "provenance", "readback_source", "source_freshness", "observed_at",
    "human_allow", "native_glpi_readmy_attested",
    "real_glpi_writes_allowed", "live_effects_allowed", "host_e2e_qualified"
  ];
  const ticketKeys = ["id", "status", "current_state", "transition_history_attested"];
  const exactKeys = (value, keys) =>
    Object.keys(value).length === keys.length &&
    keys.every(key => Object.prototype.hasOwnProperty.call(value, key));
  const reset = message => {
    el("sim-status").textContent = message;
    el("sim-ticket").textContent = "UNKNOWN";
    el("sim-state").textContent = "UNKNOWN";
    el("sim-run").textContent = "UNKNOWN";
    el("sim-transition").textContent = "UNKNOWN — historique non attesté";
    el("sim-worker").textContent = "UNKNOWN — aucun reçu no-effect";
    el("sim-provenance").textContent = "UNKNOWN — aucune lecture qualifiée";
  };
  const qualified = (data, attempt) => {
    if (!data || typeof data !== "object" || Array.isArray(data) ||
        !exactKeys(data, readbackKeys) ||
        data.schema !== "aiops.portal.sim-glpi-readback.v1" ||
        data.authority !== "SIMULATED_ONLY" || data.ticket_authority !== "SIMULATED_ONLY" ||
        data.state !== "RESOLVED" || data.simulated !== true ||
        data.tenant_id !== "ACME-TEST" || data.scenario_id !== "ACME-SAN-PAYMENTS" ||
        data.attempt_id !== attempt || data.mode !== "SIMULATION" ||
        data.provenance !== "SIMULATED" ||
        data.readback_source !== "CORE_AND_WORKER_INDEPENDENT_SANDBOX_GET" ||
        data.worker_receipt_status !== "SIMULATED_NO_EFFECT" ||
        data.worker_receipt_phase !== "PRE_RESOLUTION" ||
        data.worker_no_effect_verified !== true ||
        data.core_resolution_after_worker_verified !== true ||
        data.terminal_ticket_digest_verified !== true ||
        data.independent_final_read_rounds !== 2 ||
        data.source_freshness !== "UNKNOWN" || data.observed_at !== null ||
        data.human_allow !== false || data.native_glpi_readmy_attested !== false ||
        data.real_glpi_writes_allowed !== false ||
        data.live_effects_allowed !== false || data.host_e2e_qualified !== false ||
        !data.ticket || typeof data.ticket !== "object" || Array.isArray(data.ticket) ||
        !exactKeys(data.ticket, ticketKeys) ||
        typeof data.ticket.id !== "string" || !idPattern.test(data.ticket.id) ||
        !data.ticket.id.startsWith("SIM-GLPI-") ||
        data.ticket.status !== "RESOLVED" || data.ticket.current_state !== "RESOLVED" ||
        data.ticket.transition_history_attested !== false ||
        typeof data.incident_id !== "string" || typeof data.run_id !== "string" ||
        !idPattern.test(data.incident_id) || !idPattern.test(data.run_id)) return false;
    return true;
  };
  read.addEventListener("click", async () => {
    const current = ++epoch;
    reset("UNKNOWN — lecture sandbox en cours");
    const attempt = el("sim-attempt").value.trim();
    const token = el("sim-token").value;
    el("sim-token").value = "";
    if (!attemptPattern.test(attempt) || !token) {
      reset("403/401 — tentative ACME-SIM et jeton viewer requis");
      return;
    }
    read.disabled = true;
    try {
      const response = await fetch("/api/demo/acme-sim-glpi/" + encodeURIComponent(attempt), {
        method: "GET", credentials: "omit", cache: "no-store", redirect: "error",
        headers: {Accept: "application/json", Authorization: "Bearer " + token}
      });
      if (current !== epoch) return;
      if (response.status === 401) return reset("401 UNAUTHORIZED — viewer invalide");
      if (response.status === 403) return reset("403 FORBIDDEN — hors périmètre ACME-TEST");
      if (response.status !== 200) return reset("503 UNKNOWN — ticket simulé non attesté");
      const data = await response.json();
      if (current !== epoch) return;
      if (!qualified(data, attempt)) return reset("503 UNKNOWN — readback 200 non qualifié");
      el("sim-status").textContent = "SIMULATED · RESOLVED — 2 lectures Core/Worker + digest terminal vérifiés";
      el("sim-ticket").textContent = data.ticket.id;
      el("sim-state").textContent = "RESOLVED · SIMULATED";
      el("sim-run").textContent = data.incident_id + " / " + data.run_id;
      el("sim-transition").textContent = "État final RESOLVED ; historique de transition NOT_ATTESTED";
      el("sim-worker").textContent = "SIMULATED_NO_EFFECT · PRE_RESOLUTION · 0 effet";
      el("sim-provenance").textContent =
        "CORE_AND_WORKER_INDEPENDENT_SANDBOX_GET · 2 lectures · digest terminal · ACME-TEST · SIMULATED ; GLPI humain UNKNOWN ; E2E hôte UNKNOWN";
    } catch (_) {
      if (current === epoch) reset("503 UNKNOWN — Core sandbox indisponible");
    } finally {
      if (current === epoch) read.disabled = false;
    }
  });
  clear.addEventListener("click", () => {
    ++epoch;
    el("sim-attempt").value = "";
    el("sim-token").value = "";
    read.disabled = false;
    reset("UNKNOWN — session effacée");
  });
})();
