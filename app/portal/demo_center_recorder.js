"use strict";
// Local-only screen capture. No network calls, cookies, token storage or upload.
(() => {
  const consent = document.getElementById("recording-consent");
  const start = document.getElementById("record-start");
  const stop = document.getElementById("record-stop");
  const clear = document.getElementById("record-clear");
  const status = document.getElementById("recording-status");
  const preview = document.getElementById("record-preview");
  const download = document.getElementById("record-download");
  const scenario = document.getElementById("san-scenario");
  const scenarioStatus = document.getElementById("scenario-status");
  let stream = null;
  let recorder = null;
  let objectUrl = null;
  let requestEpoch = 0; // cancel a pending browser permission prompt on Clear/pagehide

  function setStatus(message) { status.textContent = message; }
  function supported() {
    return window.isSecureContext === true &&
      !!navigator.mediaDevices &&
      typeof navigator.mediaDevices.getDisplayMedia === "function" &&
      typeof window.MediaRecorder === "function";
  }
  function refresh() {
    start.disabled = !supported() || !consent.checked || recorder !== null;
    stop.disabled = recorder === null || recorder.state !== "recording";
  }
  function releaseStream() {
    if (stream) {
      for (const track of stream.getTracks()) { track.stop(); }
      stream = null;
    }
  }
  function discardVideo() {
    if (objectUrl) { URL.revokeObjectURL(objectUrl); objectUrl = null; }
    preview.removeAttribute("src");
    preview.load();
    download.hidden = true;
    download.removeAttribute("href");
    download.removeAttribute("download");
  }
  function selectMime() {
    for (const candidate of ["video/webm;codecs=vp9", "video/webm", "video/mp4"]) {
      if (MediaRecorder.isTypeSupported(candidate)) { return candidate; }
    }
    return "";
  }
  scenario.addEventListener("change", () => {
    scenarioStatus.textContent =
      "CATALOG_ONLY — " + scenario.options[scenario.selectedIndex].text +
      " : non exécuté. Analyst/Critic NOT_ATTESTED ; impact Payments/ERP UNKNOWN.";
  });
  function cancelCapture(message) {
    ++requestEpoch; // invalidate pending permission prompts and delayed recorder events
    const active = recorder;
    // Detach immediately: a browser may delay or omit MediaRecorder.stop.
    // A canceled session must not block a fresh, consented recording.
    recorder = null;
    if (active && active.state === "recording") {
      try { active.stop(); } catch (_) { /* stream cleanup below still applies */ }
    }
    releaseStream();
    discardVideo();
    setStatus(message);
    refresh();
  }
  consent.addEventListener("change", () => {
    if (!consent.checked) {
      cancelCapture("CONSENT_WITHDRAWN — capture arrêtée et vidéo effacée.");
    } else {
      refresh();
    }
  });
  start.addEventListener("click", async () => {
    if (!supported() || !consent.checked || recorder) {
      setStatus("BLOCKED — consentement, HTTPS/localhost et API navigateur requis.");
      return;
    }
    const epoch = ++requestEpoch;
    discardVideo();
    setStatus("PERMISSION_PENDING — choisissez explicitement un onglet de démonstration.");
    start.disabled = true;
    try {
      const selectedStream = await navigator.mediaDevices.getDisplayMedia({
        video: { displaySurface: "browser" }, audio: false
      });
      if (epoch !== requestEpoch) {
        for (const track of selectedStream.getTracks()) { track.stop(); }
        return;
      }
      stream = selectedStream;
      const mimeType = selectMime();
      recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const active = recorder;
      const recordedChunks = []; // per-session: never leak canceled chunks to a new capture
      active.addEventListener("dataavailable", (event) => {
        if (event.data && event.data.size > 0) { recordedChunks.push(event.data); }
      });
      active.addEventListener("error", () => {
        if (recorder === active) {
          cancelCapture("ERROR — capture interrompue, vidéo effacée.");
        }
      });
      active.addEventListener("stop", () => {
        if (stream === selectedStream) {
          releaseStream();
        } else {
          for (const track of selectedStream.getTracks()) { track.stop(); }
        }
        if (recorder === active) { recorder = null; }
        if (epoch !== requestEpoch) { refresh(); return; }
        if (recordedChunks.length === 0) {
          setStatus("EMPTY — aucune vidéo capturée.");
          refresh();
          return;
        }
        const blob = new Blob(recordedChunks, { type: active.mimeType || "video/webm" });
        objectUrl = URL.createObjectURL(blob);
        preview.src = objectUrl;
        download.href = objectUrl;
        download.download = "acme-demo-local." +
          (blob.type.includes("mp4") ? "mp4" : "webm");
        download.hidden = false;
        setStatus("LOCAL_ONLY — capture arrêtée. Lecture et export manuel disponibles ; NON ATTESTÉ.");
        refresh();
      }, { once: true });
      for (const track of stream.getVideoTracks()) {
        track.addEventListener("ended", () => {
          if (recorder === active && active.state === "recording") { active.stop(); }
        }, { once: true });
      }
      active.start(1000);
      setStatus("RECORDING_LOCAL — capture en cours, aucune donnée transmise au serveur.");
      refresh();
    } catch (error) {
      if (epoch !== requestEpoch) { return; }
      releaseStream();
      recorder = null;
      setStatus("DENIED_OR_UNAVAILABLE — partage refusé, annulé ou non supporté. Aucune vidéo.");
      refresh();
    }
  });
  stop.addEventListener("click", () => {
    if (recorder && recorder.state === "recording") {
      stop.disabled = true;
      setStatus("STOPPING — finalisation locale en cours.");
      recorder.stop();
    }
  });
  clear.addEventListener("click", () => {
    cancelCapture("CLEARED — aucune vidéo conservée.");
  });
  window.addEventListener("pagehide", () => {
    cancelCapture("PAGEHIDE — capture arrêtée et vidéo effacée.");
  }, { once: true });
  if (!window.isSecureContext) {
    setStatus("BLOCKED_INSECURE_ORIGIN — HTTPS ou localhost requis pour enregistrer.");
  } else if (!supported()) {
    setStatus("UNSUPPORTED — capture d'écran non disponible dans ce navigateur.");
  }
  refresh();
})();
