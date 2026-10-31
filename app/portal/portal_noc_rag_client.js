(() => {
  const asset = document.getElementById("noc-rag-asset");
  const token = document.getElementById("noc-rag-token");
  const read = document.getElementById("noc-rag-read");
  const clear = document.getElementById("noc-rag-clear");
  const status = document.getElementById("noc-rag-status");
  const output = document.getElementById("noc-rag-output");

  clear.addEventListener("click", () => {
    asset.value = "";
    token.value = "";
    output.textContent = "Aucune donnée.";
    status.textContent = "UNKNOWN — champs effacés";
  });

  read.addEventListener("click", async () => {
    const id = asset.value.trim();
    const bearer = token.value;
    token.value = "";
    if (!/^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$/.test(id) || bearer.length < 32 || bearer.length > 256) {
      status.textContent = "UNKNOWN — identifiant ou jeton invalide";
      return;
    }
    status.textContent = "Lecture du catalogue synthétique…";
    output.textContent = "Chargement…";
    try {
      const response = await fetch("/api/noc/demo-rag?asset=" + encodeURIComponent(id), {
        method: "GET",
        headers: {"Authorization": "Bearer " + bearer},
        credentials: "same-origin",
        cache: "no-store"
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || ("HTTP " + response.status));
      output.textContent = JSON.stringify(payload, null, 2);
      status.textContent = payload.state + " — " + payload.citations.length + " référence(s) synthétique(s)";
    } catch (error) {
      output.textContent = "Aucune référence exploitable.";
      status.textContent = "UNKNOWN — " + error.message;
    }
  });
})();
