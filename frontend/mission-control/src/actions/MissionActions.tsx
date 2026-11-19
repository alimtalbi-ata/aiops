import { useState, useRef } from "react";

type Result = { http: number; data: unknown };
export function MissionActions() {
  const [token, setToken] = useState("");
  const [session, setSession] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [cursor, setCursor] = useState(0);
  const [run, setRun] = useState("");
  const [asset, setAsset] = useState("brocade-fc01");
  const [context, setContext] = useState("");
  const generation = useRef(0);
  const lock = useRef(false);
  const clear = () => {
    generation.current++;
    setSession(false); setResult(null); setCursor(0); setContext(""); setRun("");
  };
  async function call(path: string, body?: object) {
    if (lock.current || !token) return;
    lock.current = true; setBusy(true); setResult(null);
    const epoch = generation.current;
    try {
      const res = await fetch("/api/mission-actions/" + path, {
        method: body ? "POST" : "GET", cache: "no-store", redirect: "error",
        credentials: "omit", headers: { Authorization: "Bearer " + token,
          ...(body ? {"Content-Type": "application/json"} : {}) },
        ...(body ? {body: JSON.stringify(body)} : {}),
      });
      const data = await res.json();
      if (epoch !== generation.current) return;
      if (res.status === 401 || res.status === 403) clear();
      else {
        if (path === "session") setSession(res.ok && data.session_kind === "SHARED_VIEWER");
        if (path === "journey" && res.ok && data.runtime_attested === false)
          setContext(String(data.incident_id) + " / " + String(data.run_id));
        if (path === "story" && res.ok && data.schema === "aiops.acme-explore-story.v1" &&
            data.runtime_attested === false && Number.isInteger(data.cursor)) setCursor(data.cursor);
        setResult({http: res.status, data});
      }
    } catch {
      if (epoch === generation.current) setResult({http: 0, data: {state: "UNKNOWN", reason: "NETWORK_OR_RESPONSE_ERROR"}});
    } finally { lock.current = false; setBusy(false); }
  }
  return <section aria-label="Mission Actions">
    <h2>Parcours opérateur — DEMO synthétique</h2>
    <p>Session viewer uniquement. Aucun droit tenant, aucune remédiation LIVE.</p>
    <label>Jeton viewer <input type="password" autoComplete="off" value={token}
      onChange={e => {clear(); setToken(e.target.value);}} /></label>
    <button disabled={busy || !token} onClick={() => void call("session")}>Vérifier la session</button>
    <button onClick={() => {clear(); setToken("");}}>Déconnexion locale</button>
    <p role="status">{session ? "Viewer vérifié" : "Session non vérifiée"} · {context || "Aucun scénario sélectionné"}</p>
    <fieldset disabled={!session || busy}>
      <legend>Scénario SAN → Payments (simulation)</legend>
      <button onClick={() => void call("journey")}>Charger Incident / Twin / Analyst / Critic / Policy / Evidence</button>
      <p>Demo Theater · navigation de checkpoints fictifs · curseur {cursor}</p>
      {["start","advance","pause","reset","replay"].map(action =>
        <button key={action} onClick={() => void call("story", {action, cursor, mode: "story"})}>{action}</button>)}
      <label>Asset fictif <input value={asset} onChange={e => setAsset(e.target.value)} /></label>
      <button onClick={() => void call("rag?asset=" + encodeURIComponent(asset))}>Références RAG synthétiques</button>
      <label>Run Core explicite <input value={run} onChange={e => setRun(e.target.value)} /></label>
      <button disabled={!run.trim()} onClick={() => void call("run/" + encodeURIComponent(run.trim()))}>Consulter Run</button>
      <button onClick={() => void call("glpi")}>Vérifier disponibilité GLPI</button>
    </fieldset>
    <p>FS Lab, inférence IA réelle, Policy runtime, HITL, Temporal et collecte Evidence : bloqués sans contrat autorisé qualifié.</p>
    {result && <div role="status"><p>HTTP {result.http || "indisponible"} — réponse technique, pas une réussite métier.</p>
      <pre style={{whiteSpace:"pre-wrap", overflowWrap:"anywhere"}}>{JSON.stringify(result.data, null, 2)}</pre></div>}
  </section>;
}
