"use strict";
/* Operator shell. Only reads a PUBLIC, explicitly synthetic local fixture and
 * an OIDC SESSION STATUS. Never reads a tenant Run, sends a bearer, writes
 * operational state or promotes a synthetic assertion to runtime authority.
 */
(() => {
  const byId = (id) => document.getElementById(id);
  const sections = ["overview", "journey", "runs", "connections"];
  const names = {
    overview: "Vue d'ensemble", journey: "Parcours SAN → Payments",
    runs: "Incidents et Runs", connections: "Accès et connexions"
  };
  const explanations = {
    fc: "Référence : un défaut sur la fabric FC pourrait affecter Payments. Le chemin affiché provient d'une fixture locale.",
    multipath: "Hypothèse à qualifier : mesurer les chemins RHEL et la redondance. Aucun replay multipath n'est lancé.",
    controller: "Hypothèse à qualifier : vérifier les états et journaux des contrôleurs. Aucune bascule n'est exécutée.",
    neighbor: "Hypothèse à qualifier : corréler la contention avec le service. Aucun indicateur réel n'est lu.",
    replication: "Hypothèse à qualifier : dater les mesures de lag. Aucune réplication n'est modifiée.",
    capacity: "Hypothèse à qualifier : rapprocher seuils, capacité et tendance. Aucun volume réel n'est interrogé.",
    change: "Hypothèse à qualifier : comparer les changements approuvés aux premières alertes. Aucun changement n'est appliqué.",
    storm: "Hypothèse à qualifier : distinguer faux positifs et incidents réels. Aucune alarme n'est supprimée."
  };
  function viewFromLocation() {
    const candidate = location.hash.slice(1);
    if (sections.includes(candidate)) return candidate;
    return location.pathname === "/runs" ? "runs" : "overview";
  }
  function setView(which) {
    const current = sections.includes(which) ? which : "overview";
    for (const name of sections) {
      byId(name).hidden = name !== current;
    }
    for (const link of document.querySelectorAll(".side-nav a[data-view]")) {
      if (link.dataset.view === current) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    }
    byId("active-view").textContent = names[current];
    document.title = names[current] + " · AIOps2";
    if (current === "connections") void checkSession();
  }
  document.addEventListener("click", (event) => {
    const target = event.target.closest("a[data-view]");
    if (!target) return;
    const name = target.dataset.view;
    if (!sections.includes(name)) return;
    event.preventDefault();
    if (location.hash !== "#" + name) location.hash = name;
    else setView(name);
  });
  window.addEventListener("hashchange", () => setView(viewFromLocation()));

  function validFixture(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value) &&
      value.schema === "aiops.synthetic-impact-read-model.v1" &&
      value.entrypoint === "/demo-center" &&
      value.provenance === "SIMULATED_TARGET" &&
      value.evidence_source === "LOCAL_SYNTHETIC_FIXTURE" &&
      value.source_artifact === "app/portal/acme-fixtures.json" &&
      value.run_id_provenance === "DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN" &&
      value.runtime_attested === false &&
      value.runtime_evidence_present === false &&
      value.production_qualified === false &&
      value.live_remediation_authorized === false &&
      value.ticket_id === null &&
      typeof value.source_sha256 === "string" &&
      /^[a-f0-9]{64}$/.test(value.source_sha256) &&
      Number.isSafeInteger(value.ci_count) && value.ci_count >= 1 && value.ci_count <= 64 &&
      Array.isArray(value.impact_path) && value.impact_path.length >= 2 &&
      value.impact_path.length <= 12 &&
      value.impact_path.every((node) => typeof node === "string" &&
        node.length > 0 && node.length <= 100);
  }
  async function loadFixture() {
    const status = byId("fixture-status");
    const path = byId("impact-path");
    status.textContent = "Lecture du modèle synthétique local…";
    status.dataset.state = "";
    byId("ci-count").textContent = "—";
    byId("fixture-provenance").textContent = "Non vérifiée";
    byId("fixture-hash").textContent = "Empreinte indisponible";
    path.replaceChildren();
    try {
      const response = await fetch("/api/demo/acme-impact", {
        credentials: "omit", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }
      });
      if (!response.ok) throw new Error("SYNTHETIC_SOURCE_UNAVAILABLE");
      const raw = await response.text();
      if (raw.length > 32768) throw new Error("SOURCE_TOO_LARGE");
      const data = JSON.parse(raw);
      if (!validFixture(data)) throw new Error("SOURCE_CONTRACT_UNQUALIFIED");
      for (const node of data.impact_path) {
        const li = document.createElement("li");
        li.textContent = node; // never parse fixture content as HTML
        path.appendChild(li);
      }
      byId("ci-count").textContent = String(data.ci_count);
      byId("fixture-provenance").textContent = "SIMULATED_TARGET · source locale";
      byId("fixture-hash").textContent = "SHA-256 " + data.source_sha256.slice(0, 16) + "…";
      status.textContent = "Référence locale chargée · Graphe et chiffres synthétiques, pas de télémétrie SAN réelle.";
      status.dataset.state = "ready";
    } catch (_) {
      byId("ci-count").textContent = "—";
      const li = document.createElement("li");
      li.className = "empty-step";
      li.textContent = "Le modèle local n'est pas disponible.";
      path.appendChild(li);
      status.textContent = "Modèle de démonstration indisponible ou non qualifié. Aucun impact métier n'est revendiqué.";
      status.dataset.state = "fail";
    }
  }
  byId("refresh-fixture").addEventListener("click", () => void loadFixture());

  const select = byId("scenario-select");
  select.addEventListener("change", () => {
    byId("scenario-description").textContent = explanations[select.value] ||
      "Hypothèse indisponible. Aucune exécution lancée.";
  });

  // Drain the small, same-origin session status response before updating the
  // UI. Otherwise Chromium can keep a 401 fetch in flight and abort it when
  // the operator navigates to DemoCenter; no body is retained or displayed.
  async function finishSessionResponse(response) {
    if (!response.body) return;
    const reader = response.body.getReader();
    let bytes = 0;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) return;
      bytes += value ? value.byteLength : 0;
      if (bytes > 8192) {
        await reader.cancel();
        throw new Error("SESSION_RESPONSE_TOO_LARGE");
      }
    }
  }

  let checkingSession = false;
  async function checkSession() {
    if (checkingSession) return;
    checkingSession = true;
    const text = byId("session-status");
    text.textContent = "Vérification des droits en cours…";
    try {
      const response = await fetch("/api/portal/session", {
        credentials: "same-origin", cache: "no-store", redirect: "error",
        headers: { Accept: "application/json" }
      });
      await finishSessionResponse(response);
      if (response.status === 401) {
        text.textContent = "Aucune session d'entreprise valide. Les données opérationnelles restent protégées.";
      } else if (response.status === 503) {
        text.textContent = "Session éventuellement présente, mais droits métier Core/GLPI non qualifiés. Aucune donnée de Run ne sera révélée.";
      } else {
        // A future HTTP 200 cannot be mistaken for a Core/GLPI tenant ACL.
        text.textContent = "État d'autorisation non attesté : l'authentification seule ne donne pas accès aux incidents.";
      }
    } catch (_) {
      text.textContent = "Le service de session est indisponible. Aucune donnée réelle n'est chargée.";
    } finally {
      checkingSession = false;
    }
  }
  byId("check-session").addEventListener("click", () => void checkSession());
  if (location.protocol !== "https:") {
    const link = byId("sso-link");
    link.removeAttribute("href");
    link.setAttribute("aria-disabled", "true");
    link.title = "Connexion d'entreprise : origine HTTPS requise";
    byId("secure-origin-hint").textContent =
      "La page est ouverte en HTTP. Une URL HTTPS configurée est nécessaire pour la connexion OIDC et pour la capture vidéo du navigateur.";
  } else {
    byId("secure-origin-hint").textContent =
      "L'accès réel requiert un fournisseur OIDC configuré, puis la validation serveur des droits Core et GLPI.";
  }
  setView(viewFromLocation());
  void loadFixture();
})();
