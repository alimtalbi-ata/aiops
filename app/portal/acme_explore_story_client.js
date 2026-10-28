/* Explore/Story uses one local SIMULATED_TARGET read model. No LIVE commands. */
(() => {
  "use strict";
  const byId = id => document.getElementById(id);
  const actions = ["start", "pause", "advance", "reset", "replay"];
  let mode = "explore";
  let cursor = 0;
  let credential = "";
  let epoch = 0;
  let timer = null;
  // Pin the scenario identity for the entire authenticated browser session.
  // A changed fixture requires an explicit Clear before another projection is shown.
  let sessionIdentity = null;

  function stopTimer() {
    if (timer !== null) clearTimeout(timer);
    timer = null;
  }
  function unknown(message) {
    stopTimer();
    byId("story-status").textContent = "UNKNOWN — " + message;
    byId("scenario").textContent = "UNKNOWN — aucune lecture vérifiée";
    byId("source").textContent = "Provenance : UNKNOWN";
    byId("step-title").textContent = "UNKNOWN";
    byId("step-detail").textContent = "Aucune preuve runtime attestée";
    byId("timeline").replaceChildren();
    const li = document.createElement("li");
    li.textContent = "UNKNOWN — données non vérifiées";
    byId("timeline").appendChild(li);
  }
  function valid(data, action, requestedCursor) {
    if (!data || typeof data !== "object" ||
        data.schema !== "aiops.acme-explore-story.v1" ||
        data.provenance !== "SIMULATED_TARGET" ||
        data.runtime_attested !== false || data.production_qualified !== false ||
        data.live_remediation_authorized !== false ||
        data.mode !== mode || data.action !== action ||
        !Number.isInteger(data.cursor) || data.cursor < 0 ||
        !Array.isArray(data.timeline) || data.timeline.length < 1 ||
        data.timeline.length > 30 || data.cursor >= data.timeline.length ||
        typeof data.source_sha256 !== "string" ||
        !/^[a-f0-9]{64}$/.test(data.source_sha256) ||
        typeof data.playing !== "boolean" || !data.scenario ||
        typeof data.scenario !== "object" ||
        data.scenario.ticket_id !== null || data.scenario.event_timestamp_utc !== null ||
        typeof data.scenario.run_id !== "string" ||
        !data.scenario.run_id.startsWith("SIM-ACME-") ||
        !Array.isArray(data.scenario.impact_path) ||
        data.scenario.impact_path.length < 2 ||
        !data.scenario.impact_path.every(s => typeof s === "string" && s.length < 100)) return false;
    const last = data.timeline.length - 1;
    const expectedCursor = action === "reset" || action === "replay" ||
      (action === "start" && requestedCursor === last) ? 0 :
      action === "advance" ? Math.min(requestedCursor + 1, last) : requestedCursor;
    const expectedPlaying = mode === "story" &&
      ["start", "advance", "replay"].includes(action) && expectedCursor < last;
    if (data.cursor !== expectedCursor || data.playing !== expectedPlaying) return false;
    if (typeof data.scenario.incident_id !== "string" ||
        typeof data.scenario.impact_incident_id !== "string" ||
        !/^ACME-DEMO-[A-Z0-9-]+$/.test(data.scenario.incident_id) ||
        !/^ACME-DEMO-[A-Z0-9-]+$/.test(data.scenario.impact_incident_id)) return false;
    for (const step of data.timeline) {
      if (!step || typeof step !== "object" || step.status !== "MISSING" ||
          !["cue", "service", "view"].every(k => typeof step[k] === "string" &&
          /^[a-z][a-z0-9_]{1,49}$/.test(step[k]))) return false;
    }
    const expected = data.timeline[data.cursor];
    if (!data.step || !["cue", "service", "view", "status"].every(k => data.step[k] === expected[k])) return false;
    const identity = JSON.stringify([data.source_sha256, data.scenario, data.timeline]);
    return sessionIdentity === null || identity === sessionIdentity;
  }
  function render(data) {
    if (sessionIdentity === null) {
      sessionIdentity = JSON.stringify([data.source_sha256, data.scenario, data.timeline]);
    }
    cursor = data.cursor;
    byId("story-status").textContent =
      (data.playing ? "STORY EN COURS" : "PAUSE / EXPLORE") +
      " — SIMULATED_TARGET · " + (cursor + 1) + "/" + data.timeline.length +
      " · aucune preuve LIVE";
    byId("scenario").textContent = data.scenario.run_id + " · " +
      data.scenario.incident_id + " → " + data.scenario.impact_incident_id +
      " · " + data.scenario.impact_path.join(" → ");
    byId("source").textContent = "Fixture SHA-256 : " + data.source_sha256 +
      " · ticket GLPI réel : ABSENT";
    byId("step-title").textContent = data.step.cue.toUpperCase() +
      " · " + data.step.service.toUpperCase();
    byId("step-detail").textContent = data.step.view + " · preuve MISSING" +
      " · runtime UNKNOWN";
    const list = byId("timeline");
    list.replaceChildren();
    data.timeline.forEach((step, i) => {
      const li = document.createElement("li");
      li.textContent = (i + 1) + ". " + step.cue + " / " + step.service +
        " — MISSING (simulation)";
      if (i === cursor) {
        li.className = "current";
        li.setAttribute("aria-current", "step");
      }
      list.appendChild(li);
    });
    if (data.playing) {
      timer = setTimeout(() => { timer = null; control("advance"); }, 1800);
    }
  }
  async function control(action) {
    if (!actions.includes(action)) return;
    stopTimer();
    const requestId = ++epoch;
    const input = byId("story-token");
    if (input.value) {
      credential = input.value;
      input.value = "";
    }
    if (!credential) {
      unknown("jeton viewer requis");
      return;
    }
    byId("story-status").textContent = "UNKNOWN — contrôle authentifié en cours";
    try {
      const response = await fetch("/api/demo/explore-story/control", {
        method: "POST", credentials: "omit", cache: "no-store", redirect: "error",
        headers: {"Content-Type": "application/json", Authorization: "Bearer " + credential},
        body: JSON.stringify({action, cursor, mode})
      });
      if (requestId !== epoch) return;
      if (!response.ok) {
        credential = "";
        unknown("contrôle refusé (" + response.status + ")");
        return;
      }
      const data = await response.json();
      if (requestId !== epoch) return;
      if (!valid(data, action, cursor)) {
        credential = "";
        unknown("enveloppe synthétique invalide");
        return;
      }
      render(data);
    } catch (_) {
      if (requestId === epoch) {
        credential = "";
        unknown("service indisponible");
      }
    }
  }
  function selectMode(next) {
    ++epoch;
    stopTimer();
    mode = next;
    cursor = 0;
    byId("mode-explore").setAttribute("aria-pressed", String(mode === "explore"));
    byId("mode-story").setAttribute("aria-pressed", String(mode === "story"));
    byId("mode-description").textContent = mode === "story"
      ? "Story : Start/Replay déroule les checkpoints fictifs. Pause interrompt la lecture."
      : "Explore : Advance parcourt manuellement les mêmes checkpoints fictifs.";
    unknown("mode modifié, relancer une lecture authentifiée");
  }
  byId("mode-explore").addEventListener("click", () => selectMode("explore"));
  byId("mode-story").addEventListener("click", () => selectMode("story"));
  for (const action of actions) {
    byId(action).addEventListener("click", () => control(action));
  }
  byId("clear").addEventListener("click", () => {
    ++epoch;
    credential = "";
    cursor = 0;
    sessionIdentity = null;
    byId("story-token").value = "";
    unknown("session effacée");
  });
})();
