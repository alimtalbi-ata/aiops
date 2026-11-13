/**
 * SAN → Payments demonstration navigation, read-only and deliberately unbound.
 * Only caller-provided, authorized, tenant-scoped records may populate steps.
 * No operational status, identity, evidence or decision is inferred.
 */
export const SAN_PAYMENTS_STEPS = Object.freeze([
  ['incident', 'Incident'],
  ['impact', 'Impact métier Payments'],
  ['noc', 'Investigation NOC'],
  ['run', 'Run'],
  ['evidence', 'Evidence'],
  ['policy', 'Critic / Policy / HITL'],
  ['decision', 'Décision humaine'],
  ['result', 'Résultat SIMULATION_ONLY']
].map(([id, label]) => Object.freeze({ id, label })));

const ALLOWED = new Set(['LOADING', 'EMPTY', 'ERROR', 'UNKNOWN', 'BLOCKED', 'AVAILABLE']);
const GUIDANCE = Object.freeze({
  LOADING: 'Attendre la réponse de la source autorisée.',
  EMPTY: 'Vérifier la période et les filtres.',
  ERROR: 'Réessayer ou contacter le support avec le contexte de la vue.',
  UNKNOWN: 'Vérifier la source avant de conclure.',
  BLOCKED: 'Vérifier les droits et la décision Policy/HITL.',
  AVAILABLE: 'Consulter la provenance avant toute interprétation.'
});
// Treat explicitly declared synthetic variants as demo-only; never infer LIVE from a label.
const isSyntheticSource = source => /^SYNTHETIC(?:$|[\s:/.\-_])/i.test(source);
// Remove bidirectional override/isolate controls and non-printing C0/C1 controls
// from untrusted adapter labels before displaying provenance or timestamps.
// Text-only DOM rendering prevents HTML injection but not visual bidi spoofing.
const text = value => {
  if (typeof value !== 'string') return null;
  const cleaned = value.replace(/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g, ' ').trim();
  return cleaned || null;
};

/** Explicitly never interprets a missing record as completed or approved. */
export function describeSanPaymentsJourney(records = {}) {
  // A null/primitive response must never crash the demo or imply an available step.
  const safeRecords = records !== null && typeof records === 'object' ? records : {};
  return SAN_PAYMENTS_STEPS.map(step => {
    // Adapter records may contain throwing accessors or Proxies. A failed read
    // must not remove the journey or turn a partial record into a claim.
    let state = 'UNKNOWN';
    let detail = 'Aucune information vérifiée';
    let source = 'Source non renseignée';
    let observedAt = 'Fraîcheur inconnue';
    try {
      const record = Object.hasOwn(safeRecords, step.id) ? safeRecords[step.id] : null;
      if (record !== null && typeof record === 'object' && !Array.isArray(record)) {
        // Only explicit adapter fields are accepted: inherited prototype values
        // must not forge state, provenance or timestamps in the operator cockpit.
        const candidate = Object.hasOwn(record, 'state') ? record.state : null;
        if (ALLOWED.has(candidate)) {
          const nextDetail = Object.hasOwn(record, 'detail') ? text(record.detail) : null;
          const nextSource = Object.hasOwn(record, 'source') ? text(record.source) : null;
          const nextObservedAt = Object.hasOwn(record, 'observedAt') ? text(record.observedAt) : null;
          state = candidate;
          detail = nextDetail ?? detail;
          source = nextSource ?? source;
          observedAt = nextObservedAt ?? observedAt;
        }
      }
    } catch {
      // A getter/Proxy may throw after state was read: discard the entire partial record.
      state = 'UNKNOWN';
      detail = 'Aucune information vérifiée';
      source = 'Source non renseignée';
      observedAt = 'Fraîcheur inconnue';
    }
    return Object.freeze({
      id: step.id, label: step.label, state, guidance: GUIDANCE[state],
      detail, source, observedAt, isOperationalClaim: false
    });
  });
}

/**
 * Accessible ordered journey. Host owns auth, navigation, data and lifecycle.
 * No inline handlers, HTML injection, network calls or synthetic operational data.
 */
export function renderSanPaymentsJourney(document, parent, records = {}, options = {}) {
  // Mode is an explicit host declaration, never inferred from records or a URL.
  // This read-only component cannot attest LIVE authorization or runtime health.
  let declaredMode = 'UNKNOWN';
  try {
    if (options && typeof options === 'object') {
      // Read once: an accessor or Proxy may return different values on successive reads.
      // Only an own host declaration counts; inherited mode metadata is untrusted.
      const mode = Object.hasOwn(options, 'mode') ? options.mode : null;
      if (mode === 'DEMO' || mode === 'REPLAY') declaredMode = mode;
    }
  } catch { /* Invalid adapter metadata fails closed to UNKNOWN. */ }
  const nav = document.createElement('nav');
  // Expose the same fail-closed mode to CSS and assistive technology without implying LIVE.
  nav.setAttribute('data-mode', declaredMode);
  nav.setAttribute('aria-label', 'Parcours SAN vers Payments — mode ' + declaredMode);
  const heading = document.createElement('h2');
  heading.textContent = 'SAN → Payments';
  const note = document.createElement('p');
  const modeExplanation = {
    UNKNOWN: 'mode non attesté, LIVE non revendiqué.',
    DEMO: 'démonstration uniquement, aucune opération LIVE.',
    REPLAY: 'rejeu déclaré, données historiques non attestées ; aucune opération LIVE.'
  }[declaredMode];
  note.textContent = 'Mode : ' + declaredMode + ' — ' + modeExplanation +
    ' Étapes de démonstration : aucune validation opérationnelle implicite.';
  const steps = describeSanPaymentsJourney(records);
  const list = document.createElement('ol');
  for (const step of steps) {
    const item = document.createElement('li');
    item.setAttribute('data-step', step.id);
    item.setAttribute('data-state', step.state);
    // Styling hook only: declared metadata is not proof of LIVE freshness or trust.
    item.setAttribute('data-provenance', isSyntheticSource(step.source) ? 'SYNTHETIC' :
      (step.source === 'Source non renseignée' || step.observedAt === 'Fraîcheur inconnue') ?
        'INCOMPLETE' : 'DECLARED_UNVERIFIED');
    // Freshness is orthogonal to source provenance: synthetic records can also lack a timestamp.
    item.setAttribute('data-freshness', step.observedAt === 'Fraîcheur inconnue' ? 'UNKNOWN' : 'DECLARED_UNVERIFIED');
    // Native busy semantics are scoped to the pending step, never the whole journey.
    if (step.state === 'LOADING') item.setAttribute('aria-busy', 'true');
    const label = document.createElement('strong');
    label.textContent = step.label;
    const status = document.createElement('span');
    status.textContent = 'État : ' + step.state + (step.state === 'AVAILABLE' ? ' (données consultables, non validées)' : '');
    const detail = document.createElement('p');
    detail.textContent = step.detail;
    const guidance = document.createElement('p');
    guidance.textContent = step.guidance;
    const provenance = document.createElement('small');
    provenance.textContent = (step.source === 'Source non renseignée' ? 'PROVENANCE INCOMPLÈTE — source non vérifiable · ' : '') +
      (step.observedAt === 'Fraîcheur inconnue' ? 'FRAÎCHEUR INCONNUE — aucune date vérifiée · ' : '') +
      (isSyntheticSource(step.source) ? 'DONNÉES SYNTHÉTIQUES — démonstration uniquement · ' : '') +
      'Source déclarée : ' + step.source + ' · Horodatage déclaré : ' + step.observedAt;
    item.append(label, status, detail, guidance, provenance);
    list.append(item);
  }
  // These counts describe only the eight displayed stages, never platform health.
  const unknown = steps.filter(step => step.state === 'UNKNOWN').length;
  const errors = steps.filter(step => step.state === 'ERROR').length;
  const empty = steps.filter(step => step.state === 'EMPTY').length;
  const unresolved = unknown + errors + empty;
  const blocked = steps.filter(step => step.state === 'BLOCKED').length;
  const loading = steps.filter(step => step.state === 'LOADING').length;
  const consultable = steps.filter(step => step.state === 'AVAILABLE').length;
  const incompleteSource = steps.filter(step => step.source === 'Source non renseignée').length;
  const unknownFreshness = steps.filter(step => step.observedAt === 'Fraîcheur inconnue').length;
  const synthetic = steps.filter(step => isSyntheticSource(step.source)).length;
  const summary = document.createElement('p');
  summary.textContent = 'Couverture de la démonstration : ' + unresolved +
    ' étape(s) sans information exploitable (UNKNOWN : ' + unknown +
    ', ERROR : ' + errors + ', EMPTY : ' + empty + ') ; ' + blocked +
    ' étape(s) bloquée(s) ; ' + loading +
    ' étape(s) en chargement ; ' + consultable +
    ' étape(s) consultable(s), non validée(s). Provenance déclarée : ' + incompleteSource +
    ' source(s) non renseignée(s), ' + unknownFreshness +
    ' horodatage(s) inconnu(s), ' + synthetic +
    ' source(s) SYNTHETIC (démonstration uniquement). Les horodatages renseignés sont déclaratifs et ne prouvent pas la fraîcheur. Comptage des étapes affichées uniquement, pas un indicateur de santé.';
  nav.append(heading, note, list, summary);
  parent.append(nav);
  return nav;
}
