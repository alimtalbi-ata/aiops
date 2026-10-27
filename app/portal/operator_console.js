"use strict";
(() => {
  // Bearer token lives in this closure only: never URL, cookie or web storage.
  let bearer = null;
  const names = ["incidents", "runs", "evidence"];
  const fields = {
    incidents: ["incident_id", "severity", "state", "title", "synthetic"],
    runs: ["run_id", "incident_id", "mode", "status"],
    evidence: ["evidence_id", "source", "claim", "payload_hash"]
  };
  const $ = (id) => document.getElementById(id);
  function reset() {
    for (const name of names) {
      $(name + "-state").textContent = "UNKNOWN";
      $(name + "-items").replaceChildren();
    }
    $("role-state").textContent = "Rôle : UNKNOWN";
  }
  function clear() {
    bearer = null;
    $("token").value = "";
    reset();
    $("auth-state").textContent = "UNKNOWN — session effacée";
  }
  function project(name, snapshot) {
    const state = snapshot.states[name];
    if (!["READABLE_UNVERIFIED", "UNKNOWN", "FORBIDDEN_BY_ROLE"].includes(state)) {
      throw new Error("invalid state");
    }
    const target = $(name + "-items");
    target.replaceChildren();
    $(name + "-state").textContent = state === "READABLE_UNVERIFIED"
      ? "READABLE_UNVERIFIED — lecture API non attestée" : state;
    if (state !== "READABLE_UNVERIFIED") return;
    const envelope = snapshot.resources[name];
    if (!envelope || !Array.isArray(envelope.items) || envelope.items.length > 100) {
      throw new Error("invalid resource envelope");
    }
    for (const item of envelope.items.slice(0, 50)) {
      if (!item || typeof item !== "object" || Array.isArray(item)) {
        throw new Error("invalid item");
      }
      const line = document.createElement("li");
      // Explicit whitelist and textContent prevent markup or private fields leaking.
      line.textContent = fields[name].map((key) =>
        key + ": " + String(item[key] ?? "UNKNOWN").slice(0, 160)
      ).join(" | ");
      target.appendChild(line);
    }
  }
  async function refresh() {
    reset();
    if (!bearer) return;
    $("auth-state").textContent = "Lecture en cours…";
    try {
      const response = await fetch("/api/portal/operator/snapshot", {
        method: "GET",
        headers: { "Authorization": "Bearer " + bearer, "Accept": "application/json" },
        credentials: "omit",
        cache: "no-store",
        redirect: "error"
      });
      if (!response.ok) {
        if (response.status === 401 || response.status === 403 || response.status === 503) {
          clear();
        }
        throw new Error("API unavailable");
      }
      const snapshot = await response.json();
      if (!snapshot || snapshot.schema !== "aiops.portal.operator-read.v1"
          || snapshot.runtime_authenticated !== false
          || snapshot.live_remediation_authorized !== false
          || snapshot.provenance !== "UNATTESTED_UPSTREAM_API_READ"
          || !["viewer", "operator"].includes(snapshot.role)
          || !snapshot.states || !snapshot.resources) {
        throw new Error("invalid snapshot contract");
      }
      for (const name of names) project(name, snapshot);
      $("role-state").textContent = "Rôle : " + snapshot.role;
      $("auth-state").textContent = "API lue — aucune attestation LIVE";
    } catch (_) {
      reset();
      $("auth-state").textContent = "UNKNOWN — accès ou réponse API indisponible";
    }
  }
  $("access").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = $("token").value;
    $("token").value = "";
    if (!value || value.length < 32 || value.length > 256) {
      clear();
      $("auth-state").textContent = "UNKNOWN — jeton invalide";
      return;
    }
    bearer = value;
    void refresh();
  });
  $("clear").addEventListener("click", clear);
  window.addEventListener("pagehide", clear);
  reset();
})();
