(() => {
  const ticket = document.getElementById("glpi-ticket-id");
  const tokenInput = document.getElementById("demo-operator-token");
  const question = document.getElementById("glpi-bot-question");
  const analyze = document.getElementById("glpi-bot-analyze");
  const propose = document.getElementById("glpi-bot-propose");
  const status = document.getElementById("glpi-bot-status");
  const output = document.getElementById("glpi-bot-answer");
  let operatorToken = "";
  let analyzedTicket = "";
  let runId = "";

  function setStatus(value) { status.textContent = value; }
  function clearSensitive() {
    operatorToken = "";
    tokenInput.value = "";
  }
  function validInput() {
    const id = ticket.value.trim();
    const token = tokenInput.value;
    const q = question.value.trim();
    if (!/^\\d{1,12}$/.test(id)) throw new Error("Identifiant GLPI invalide.");
    if (token.length < 32 || token.length > 256) throw new Error("Jeton opérateur DEMO invalide.");
    if (q.length < 3 || q.length > 2000) throw new Error("Question invalide.");
    return {id, token, q};
  }

  analyze.addEventListener("click", async () => {
    propose.disabled = true;
    analyzedTicket = "";
    runId = "";
    output.textContent = "Analyse en cours…";
    try {
      const v = validInput();
      operatorToken = v.token;
      const response = await fetch("/api/copilot/glpi-ticket/" + encodeURIComponent(v.id), {
        method: "POST",
        headers: {"Authorization": "Bearer " + operatorToken, "Content-Type": "application/json"},
        body: JSON.stringify({question: v.q}),
        credentials: "same-origin",
        cache: "no-store"
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || payload.reason || ("HTTP " + response.status));
      analyzedTicket = v.id;
      runId = payload.run_link && payload.run_link.run_id || "";
      output.textContent = JSON.stringify(payload, null, 2);
      propose.disabled = !(runId && payload.run_link.status === "LINKED");
      setStatus(propose.disabled ? "Analyse terminée, mais aucun Run ACME unique n’est lié." :
        "Analyse terminée · Run " + runId + " · proposition disponible uniquement si action validée.");
    } catch (error) {
      clearSensitive();
      setStatus("Analyse indisponible : " + error.message);
      output.textContent = "Aucune proposition créée.";
    }
  });

  propose.addEventListener("click", async () => {
    propose.disabled = true;
    try {
      if (!operatorToken || !analyzedTicket || !runId) throw new Error("Relancer d’abord une analyse autorisée.");
      const response = await fetch("/api/hitl/glpi-ticket/" + encodeURIComponent(analyzedTicket) + "/proposal", {
        method: "POST",
        headers: {"Authorization": "Bearer " + operatorToken, "Content-Type": "application/json"},
        body: JSON.stringify({
          source_action_id: "CI-COLLECT-READONLY",
          question: question.value.trim()
        }),
        credentials: "same-origin",
        cache: "no-store"
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || payload.reason || ("HTTP " + response.status));
      output.textContent = JSON.stringify(payload, null, 2);
      setStatus("Proposition HITL créée · " + payload.hitl_proposal.proposal_id +
        " · état PROPOSED · exécution interdite.");
    } catch (error) {
      setStatus("Proposition non créée : " + error.message);
      output.textContent = "Aucune autorisation d’exécution n’a été accordée.";
    } finally {
      clearSensitive();
    }
  });

  window.addEventListener("pagehide", clearSensitive, {once: true});
})();
