/* One-time same-origin token exchange; never persists a credential in browser storage. */
(function () {
  'use strict';
  function routeFor(value) {
    if (typeof value !== 'string' || !/^RUN-[A-Za-z0-9][A-Za-z0-9_.-]{1,91}$/.test(value)) {
      return null;
    }
    return '/runs/' + encodeURIComponent(value);
  }
  function mount(doc, navigate, requestSession) {
    const input = doc.getElementById('run-detail-id');
    const button = doc.getElementById('run-detail-open');
    const output = doc.getElementById('run-detail-error');
    const tokenInput = doc.getElementById('portal-read-token');
    const request = requestSession || (typeof window !== 'undefined'
      ? window.fetch.bind(window) : null);
    if (!input || !button || !output) return false;
    button.addEventListener('click', async function () {
      const runId = input.value;
      const path = routeFor(runId);
      const token = tokenInput && typeof tokenInput.value === 'string'
        ? tokenInput.value : '';
      if (tokenInput) tokenInput.value = '';
      if (!path) {
        output.textContent = 'UNKNOWN — identifiant Run invalide';
        return;
      }
      if (!token) {
        output.textContent = 'UNKNOWN — jeton lecture Core requis';
        return;
      }
      if (typeof request !== 'function') {
        output.textContent = 'UNKNOWN — échange de session indisponible';
        return;
      }
      output.textContent = 'UNKNOWN — ouverture de session lecture seule';
      try {
        const response = await request('/api/portal/run-session', {
          method: 'POST',
          headers: { Authorization: 'Bearer ' + token, 'X-Portal-Run-ID': runId },
          // No browser credential/cookie may become actor+tenant authority.
          // Reject Set-Cookie even if an older endpoint returns HTTP 200.
          credentials: 'omit',
          cache: 'no-store',
          redirect: 'error'
        });
        if (response && response.ok) {
          // No positive server-derived exact-Run ACL contract is installed.
          // HTTP 2xx (including legacy session success) grants no navigation.
          output.textContent = 'UNKNOWN — session non qualifiée (ACL acteur+tenant absente)';
        } else {
          const status = response && response.status;
          output.textContent = status === 401
            ? 'UNAUTHORIZED (HTTP 401) — jeton lecture invalide'
            : status === 403
              ? 'UNAUTHORIZED (HTTP 403) — session lecture seule refusée'
              : status === 503
                ? 'UNKNOWN (HTTP 503) — ACL acteur+tenant non qualifiée'
                : 'UNKNOWN — session lecture seule refusée';
        }
      } catch (_) {
        output.textContent = 'UNKNOWN — service de session indisponible';
      }
    });
    return true;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { routeFor, mount };
  if (typeof document !== 'undefined') {
    mount(document, function (path) { window.location.assign(path); });
  }
}());
