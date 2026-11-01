"use strict";
// Portal status-only UI: never sends a browser bearer or a claimed actor/tenant.
(() => {
  const button = document.getElementById("glpi-check");
  const status = document.getElementById("glpi-check-status");
  if (!button || !status) return;
  let generation = 0;
  button.addEventListener("click", async () => {
    const current = ++generation;
    button.disabled = true;
    status.textContent = "UNKNOWN — vérification de session, aucun ticket chargé.";
    try {
      const response = await fetch("/api/portal/itsm", {
        method: "GET", credentials: "same-origin",
        cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }
      });
      if (current !== generation) return;
      // The status check never grants permission, regardless of body content.
      status.textContent = response.status === 401
        ? "401 UNAUTHORIZED — session OIDC requise ou révoquée ; aucun repli viewer."
        : "503 UNKNOWN — droits humains GLPI et liaison Core non attestés.";
    } catch (_) {
      if (current === generation) {
        status.textContent = "503 UNKNOWN — contrôle indisponible ; aucun droit accordé.";
      }
    } finally {
      if (current === generation) button.disabled = false;
    }
  });
})();
