(() => {
  "use strict";
  const token = document.getElementById("copilot-token");
  const question = document.getElementById("copilot-question");
  const button = document.getElementById("copilot-submit");
  const status = document.getElementById("copilot-status");
  if (!token || !question || !button || !status) return;
  button.addEventListener("click", async () => {
    const bearer = token.value.trim();
    const text = question.value.trim();
    token.value = "";
    if (!bearer || !text) {
      status.textContent = "UNKNOWN — jeton et question requis";
      return;
    }
    button.disabled = true;
    status.textContent = "Vérification des autorisations…";
    try {
      const r = await fetch("/api/copilot", {
        method: "POST",
        headers: {"Authorization":"Bearer " + bearer, "Content-Type":"application/json"},
        body: JSON.stringify({question:text}),
        credentials: "omit",
        cache: "no-store",
        redirect: "error"
      });
      const data = await r.json();
      if (!r.ok) {
        status.textContent = 'HTTP ' + r.status + ' — ' +
          (r.status === 401 ? "UNAUTHORIZED" : "UNKNOWN") +
          (data.reason ? " (" + data.reason + ")" : "");
        return;
      }
      status.textContent = "UNKNOWN — réponse non qualifiée";
    } catch (_) {
      status.textContent = "Copilot indisponible";
    } finally {
      button.disabled = false;
    }
  });
})();
