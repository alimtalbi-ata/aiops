/**
 * UI-only settlement adapter. A stale FS1113 success or failure is ignored.
 * Callers supply presentation callbacks; no network, DOM, or operational data.
 */
export function settleEvidenceRequest(gate, token, pending, {onSuccess, onError}) {
  if (!gate || typeof gate.isCurrent !== 'function' ||
      typeof onSuccess !== 'function' || typeof onError !== 'function') {
    return Promise.reject(new TypeError('Invalid evidence settlement adapter'));
  }
  return Promise.resolve(pending).then(
    value => {
      if (gate.isCurrent(token)) onSuccess(value);
    },
    error => {
      if (gate.isCurrent(token)) onError(error);
    }
  );
}
