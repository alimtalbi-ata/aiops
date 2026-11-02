"use strict";
// Only the ACME-TEST synthetic Core ticket readback. Never native GLPI READ/READMY.
(() => {
  const el = id => document.getElementById(id);
  const read = el("sim-read"), clear = el("sim-clear");
  if (!read || !clear) return;
  let epoch = 0;
  const attemptPattern = /^ACME-SIM-[A-Z0-9_-]{8,80}$/;
  const idPattern = /^[A-Za-z0-9][A-Za-z0-9_-]{2,99}$/;
  const reset = message => {
    el("sim-status").textContent = message;
    el("sim-ticket").textContent = "UNKNOWN";
    el("sim-state").textContent = "UNKNOWN";
    el("sim-run").textContent = "UNKNOWN";
    el("sim-transition").textContent = "UNKNOWN — historique non attesté";
    el("sim-provenance").textContent = "UNKNOWN — aucune lecture qualifiée";
  };
  const qualified = (data, attempt) => {
    if (!data || typeof data !== "object" || Array.isArray(data) ||
        data.schema !== "aiops.portal.sim-glpi-readback.v1" ||
        data.state !== "RESOLVED" || data.simulated !== true ||
        data.tenant_id !== "ACME-TEST" || data.scenario_id !== "ACME-SAN-PAYMENTS" ||
        data.attempt_id !== attempt || data.mode !== "SIMULATION" ||
        data.provenance !== "SIMULATED" ||
        data.readback_source !== "CORE_SANDBOX_READBACK" ||
        data.source_freshness !== "UNKNOWN" || data.observed_at !== null ||
        data.human_allow !== false || data.native_glpi_readmy_attested !== false ||
        data.real_glpi_writes_allowed !== false ||
        data.live_effects_allowed !== false || data.host_e2e_qualified !== false ||
        !data.ticket || typeof data.ticket !== "object" ||
        !idPattern.test(data.ticket.id) || !data.ticket.id.startsWith("SIM-GLPI-") ||
        data.ticket.status !== "RESOLVED" || data.ticket.transition_to !== "RESOLVED" ||
        data.ticket.transition_history_attested !== false ||
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
      el("sim-status").textContent = "SIMULATED · RESOLVED — Core sandbox uniquement";
      el("sim-ticket").textContent = data.ticket.id;
      el("sim-state").textContent = "RESOLVED · SIMULATED";
      el("sim-run").textContent = data.incident_id + " / " + data.run_id;
      el("sim-transition").textContent = "→ RESOLVED ; historique de transition NOT_ATTESTED";
      el("sim-provenance").textContent =
        "CORE_SANDBOX_READBACK · ACME-TEST · SIMULATED ; GLPI humain UNKNOWN ; E2E UNKNOWN";
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
