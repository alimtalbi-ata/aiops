(() => {
  const tokenInput = document.getElementById("demo-token");
  const button = document.getElementById("launch-demo");
  const status = document.getElementById("demo-launch-status");
  if (!tokenInput || !button || !status) return;

  button.addEventListener("click", async () => {
    const token = tokenInput.value.trim();
    tokenInput.value = "";
    if (!token) {
      status.textContent = "Jeton opérateur requis.";
      return;
    }
    button.disabled = true;
    status.textContent = "Création du scénario synthétique et démarrage Temporal…";
    const retryKey = (globalThis.crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : "demo-" + Date.now() + "-" + Math.random().toString(16).slice(2);
    try {
      const response = await fetch("/api/demo", {
        method: "POST",
        credentials: "omit",
        cache: "no-store",
        headers: {
          "Authorization": "Bearer " + token,
          "Idempotency-Key": retryKey
        }
      });
      const data = await response.json();
      if (!response.ok || data.state !== "STARTED" || !data.run_id) {
        status.textContent = "Lancement non confirmé : " +
          (data.reason || data.detail || "état UNKNOWN");
        return;
      }
      status.textContent = "DEMO démarrée — Run " + data.run_id +
        " · " + (data.workflow_id || "workflow en attente");
      const link = document.createElement("a");
      link.href = "/demo-studio/run/" + encodeURIComponent(data.run_id);
      link.textContent = "Ouvrir le Run";
      link.rel = "noopener";
      status.appendChild(document.createTextNode(" · "));
      status.appendChild(link);
    } catch (_) {
      status.textContent = "Lancement non confirmé — réessayer avec une nouvelle clé.";
    } finally {
      button.disabled = false;
    }
  });
})();
