(() => {
  "use strict";
  const tokenInput = document.getElementById("hitl-operator-token");
  const loadButton = document.getElementById("hitl-load-inbox");
  const inboxStatus = document.getElementById("hitl-inbox-status");
  const inboxOutput = document.getElementById("hitl-inbox-output");
  const subject = document.getElementById("hitl-sim-subject");
  const issueButton = document.getElementById("hitl-sim-issue");
  const simOutput = document.getElementById("hitl-sim-result");
  if (!tokenInput || !loadButton || !inboxStatus || !inboxOutput ||
      !subject || !issueButton || !simOutput) return;

  function bearer() {
    const value = tokenInput.value;
    if (value.length < 32 || value.length > 256) {
      throw new Error("Jeton opérateur DEMO invalide.");
    }
    return value;
  }

  loadButton.addEventListener("click", async () => {
    loadButton.disabled = true;
    inboxStatus.textContent = "Vérification de l’autorisation opérateur…";
    inboxOutput.textContent = "Chargement…";
    try {
      const response = await fetch("/api/portal/hitl/inbox", {
        method: "GET",
        headers: { "Authorization": "Bearer " + bearer() },
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error"
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || payload.reason || ("HTTP " + response.status));
      inboxOutput.textContent = JSON.stringify(payload, null, 2);
      inboxStatus.textContent = payload.count + " proposition(s) synthétique(s) · aucune approbation ni exécution";
    } catch (error) {
      inboxOutput.textContent = "Aucune donnée chargée.";
      inboxStatus.textContent = "Inbox indisponible : " + error.message;
    } finally {
      loadButton.disabled = false;
    }
  });

  issueButton.addEventListener("click", async () => {
    issueButton.disabled = true;
    simOutput.textContent = "Émission…";
    try {
      const response = await fetch("/api/portal/hitl/simulator/token", {
        method: "POST",
        headers: {
          "Authorization": "Bearer " + bearer(),
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ subject: subject.value }),
        credentials: "same-origin",
        cache: "no-store",
        redirect: "error"
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || payload.reason || ("HTTP " + response.status));
      simOutput.textContent = JSON.stringify(payload, null, 2);
    } catch (error) {
      simOutput.textContent = "Identité simulée non émise : " + error.message;
    } finally {
      issueButton.disabled = false;
    }
  });

  window.addEventListener("pagehide", () => {
    tokenInput.value = "";
  }, { once: true });
})();
