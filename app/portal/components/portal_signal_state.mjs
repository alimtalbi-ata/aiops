/**
 * Read-only Portal V3 presentation model. Never infers operational health,
 * freshness, identity, authorization or Policy/HITL decisions.
 * Caller must supply authorized, tenant-scoped data.
 */
const STATES = new Set(['LOADING', 'EMPTY', 'ERROR', 'UNKNOWN', 'BLOCKED', 'AVAILABLE']);
const LABELS = Object.freeze({
  LOADING: 'Chargement en cours',
  EMPTY: 'Aucune donnée disponible',
  ERROR: 'Données indisponibles',
  UNKNOWN: 'État non déterminé',
  BLOCKED: 'Accès ou action bloqué',
  AVAILABLE: 'Données disponibles'
});
const HINTS = Object.freeze({
  LOADING: 'Veuillez patienter.',
  EMPTY: 'Vérifiez les filtres ou la période sélectionnée.',
  ERROR: 'Réessayez ou contactez l’équipe de support.',
  UNKNOWN: 'Vérifiez la source et la fraîcheur avant toute conclusion.',
  BLOCKED: 'Vérifiez les droits et la décision Policy/HITL auprès du responsable.',
  AVAILABLE: 'Consultez la provenance et la date de collecte.'
});
const safeString = value => typeof value === 'string' && value.trim() ? value.trim() : null;

/**
 * The source and observedAt fields are untrusted labels, not proof of
 * authorization, health or recency. Never converts UNKNOWN to AVAILABLE.
 */
export function describePortalSignal(input = {}) {
  const state = STATES.has(input?.state) ? input.state : 'UNKNOWN';
  const source = safeString(input?.source);
  const observedAt = safeString(input?.observedAt);
  return Object.freeze({
    state,
    label: LABELS[state],
    hint: HINTS[state],
    sourceLabel: source ?? 'Source non renseignée',
    freshnessLabel: observedAt ? `Horodatage déclaré : ${observedAt}` : 'Fraîcheur inconnue',
    isOperationalClaim: false
  });
}

/**
 * Render using textContent only: no HTML interpolation or inline scripts.
 * Host provides a document and an authorized parent element.
 */
export function renderPortalSignal(document, parent, input) {
  const model = describePortalSignal(input);
  const section = document.createElement('section');
  section.setAttribute('aria-label', 'État et provenance');
  section.setAttribute('data-portal-state', model.state);
  const title = document.createElement('strong');
  title.textContent = model.label;
  const hint = document.createElement('p');
  hint.textContent = model.hint;
  const source = document.createElement('p');
  source.textContent = model.sourceLabel;
  const freshness = document.createElement('p');
  freshness.textContent = model.freshnessLabel;
  section.append(title, hint, source, freshness);
  parent.append(section);
  return section;
}
