/* Navigation only: never accepts, stores or transmits a credential. */
(function () {
  'use strict';
  function routeFor(value) {
    if (typeof value !== 'string' || !/^RUN-[A-Za-z0-9][A-Za-z0-9_.-]{1,91}$/.test(value)) {
      return null;
    }
    return '/runs/' + encodeURIComponent(value);
  }
  function mount(doc, navigate) {
    const input = doc.getElementById('run-detail-id');
    const button = doc.getElementById('run-detail-open');
    const output = doc.getElementById('run-detail-error');
    if (!input || !button || !output) return false;
    button.addEventListener('click', function () {
      const path = routeFor(input.value);
      if (path) navigate(path);
      else output.textContent = 'UNKNOWN — identifiant Run invalide';
    });
    return true;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = { routeFor, mount };
  if (typeof document !== 'undefined') {
    mount(document, function (path) { window.location.assign(path); });
  }
}());
