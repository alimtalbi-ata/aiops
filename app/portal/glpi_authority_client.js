"use strict";
// Portal source/freshness readiness only. Never use a browser bearer or
// a claimed actor/tenant, and never turn any upstream 200/ALLOW into access.
(() => {
  const button = document.getElementById("glpi-check");
  const status = document.getElementById("glpi-check-status");
  const provenance = document.getElementById("glpi-source-provenance");
  const fields = ["idp", "glpi", "core", "replay"];
  if (!button || !status || !provenance) return;
  let generation = 0;
  const paintUnknown = (detail) => {
    provenance.textContent = "Provenance : PORTAL_CONTRACT_ONLY ; observé à : UNKNOWN ; " +
      "fraîcheur : UNKNOWN. Core PG16 : SOURCE_CONTRACT_ONLY_NOT_HUMAN_ACL.";
    for (const key of fields) {
      const cell = document.querySelector('[data-authority-check="' + key + '"]');
      if (cell) cell.textContent = "UNKNOWN — " + detail;
    }
  };
  button.addEventListener("click", async () => {
    const current = ++generation;
    button.disabled = true;
    status.textContent = "UNKNOWN — vérification de session, aucun ticket chargé.";
    paintUnknown("en attente de preuve indépendante");
    try {
      const response = await fetch("/api/portal/itsm", {
        method: "GET", credentials: "same-origin",
        cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }
      });
      if (current !== generation) return;
      // A response body is never a source of permission. Only a strictly
      // negative 503 contract can update the source-readiness explanation.
      if (response.status === 401) {
        status.textContent = "401 UNAUTHORIZED — session OIDC requise ou révoquée ; aucun repli viewer.";
        paintUnknown("session non autorisée");
        return;
      }
      if (response.status === 403) {
        status.textContent = "403 FORBIDDEN — accès explicitement refusé ; aucun droit accordé.";
        paintUnknown("accès refusé");
        return;
      }
      if (response.status !== 503) {
        status.textContent = "503 UNKNOWN — réponse non qualifiée ; aucun droit accordé.";
        paintUnknown("réponse non qualifiée");
        return;
      }
      const data = await response.json();
      if (current !== generation) return;
      const src = data && data.authority_sources;
      const qualifiedNegative = data.schema === "aiops.portal.glpi-handoff.v1" &&
        data.state === "UNKNOWN" && data.tenant_acl_qualified === false &&
        data.runtime_attested === false && data.glpi_write_enabled === false &&
        data.human_authority && data.human_authority.human_allow === false &&
        src && src.schema === "aiops.portal.authority-sources.v1" &&
        src.provenance === "PORTAL_CONTRACT_ONLY" &&
        src.observed_at === null && src.freshness === "UNKNOWN" &&
        src.core_pg16_producer === "SOURCE_CONTRACT_ONLY_NOT_HUMAN_ACL" &&
        src.idp_glpi_mapping === "NOT_ATTESTED" &&
        src.glpi_native_readmy_ownership === "NOT_ATTESTED" &&
        src.core_run_signer_nonce_revocation === "NOT_ATTESTED" &&
        src.independent_proofs_verified === false && src.human_allow === false;
      status.textContent = "503 UNKNOWN — droits humains GLPI et liaison Core non attestés.";
      paintUnknown(qualifiedNegative ? "source indépendante non attestée" : "contrat de source non qualifié");
    } catch (_) {
      if (current === generation) {
        status.textContent = "503 UNKNOWN — contrôle indisponible ; aucun droit accordé.";
        paintUnknown("contrôle indisponible");
      }
    } finally {
      if (current === generation) button.disabled = false;
    }
  });
})();
