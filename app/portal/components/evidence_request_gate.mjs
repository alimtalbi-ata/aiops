/** Read-only UI request gate: only the most recent issued request may publish. */
export function createEvidenceRequestGate() {
  let generation = 0;
  let active = true;
  return Object.freeze({
    issue() {
      if (!active) return null;
      generation += 1;
      return generation;
    },
    isCurrent(token) {
      return active && Number.isSafeInteger(token) && token > 0 && token === generation;
    },
    invalidate() {
      generation += 1;
    },
    dispose() {
      active = false;
      generation += 1;
    }
  });
}
