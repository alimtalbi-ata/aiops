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
const text = value => typeof value === 'string' && value.trim() ? value.trim() : null;

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
        const candidate = record.state;
        if (ALLOWED.has(candidate)) {
          const nextDetail = text(record.detail);
          const nextSource = text(record.source);
          const nextObservedAt = text(record.observedAt);
          state = candidate;
          detail = nextDetail ?? detail;
          source = nextSource ?? source;
          observedAt = nextObservedAt ?? observedAt;
        }
      }
    } catch {
      // Fail closed for this step; later steps remain independently readable.
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
export function renderSanPaymentsJourney(document, parent, records = {}) {
  const nav = document.createElement('nav');
  nav.setAttribute('aria-label', 'Parcours de démonstration SAN vers Payments');
  const heading = document.createElement('h2');
  heading.textContent = 'SAN → Payments';
  const note = document.createElement('p');
  note.textContent = 'Étapes de démonstration : aucune validation opérationnelle implicite.';
  const list = document.createElement('ol');
  for (const step of describeSanPaymentsJourney(records)) {
    const item = document.createElement('li');
    item.setAttribute('data-step', step.id);
    item.setAttribute('data-state', step.state);
    const label = document.createElement('strong');
    label.textContent = step.label + ' — ' + step.state;
    const detail = document.createElement('p');
    detail.textContent = step.detail;
    const guidance = document.createElement('p');
    guidance.textContent = step.guidance;
    const provenance = document.createElement('small');
    provenance.textContent = 'Source déclarée : ' + step.source + ' · Horodatage déclaré : ' + step.observedAt;
    item.append(label, detail, guidance, provenance);
    list.append(item);
  }
  nav.append(heading, note, list);
  parent.append(nav);
  return nav;
}
