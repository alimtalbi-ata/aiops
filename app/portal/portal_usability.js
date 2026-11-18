/* Adapted from #809; presentation only, no network or persisted state. */
(function (root) {
  "use strict";
  const mounted = new WeakSet();
  function mount(doc) {
    const tbody = doc.getElementById("portal-runs");
    const filter = doc.getElementById("portal-run-filter");
    const input = doc.getElementById("portal-run-filter-input");
    const clear = doc.getElementById("portal-run-filter-clear");
    const result = doc.getElementById("portal-run-filter-result");
    if (!tbody || !filter || !input || !clear || !result) return false;
    if (mounted.has(filter)) return true;
    mounted.add(filter);
    function applyFilter() {
      const rows = Array.from(tbody.rows);
      const dataRows = rows.filter(row => row.cells.length === 5 &&
        Array.from(row.cells).every(cell => cell.tagName === "TD" && cell.colSpan === 1));
      const actualRows = new Set(dataRows);
      for (const row of rows) if (!actualRows.has(row)) row.hidden = false;
      input.disabled = dataRows.length === 0;
      if (input.disabled) input.value = "";
      const query = input.value.trim().toLowerCase();
      clear.disabled = input.disabled || !input.value;
      let visible = 0;
      for (const row of dataRows) {
        const text = Array.from(row.cells).map(cell => cell.textContent).join(" ").toLowerCase();
        const match = !query || text.includes(query);
        row.hidden = !match;
        if (match) visible += 1;
      }
      const message = input.disabled
        ? "Filtre indisponible · aucune ligne de données affichée. Voir l’état de lecture."
        : visible + " / " + dataRows.length + " Runs affichés · " +
          (visible === 0 ? "aucun résultat pour ce filtre local" : "filtre local uniquement");
      if (result.textContent !== message) result.textContent = message;
    }
    input.addEventListener("input", applyFilter);
    clear.addEventListener("click", function () {
      input.value = "";
      applyFilter();
      if (!input.disabled) input.focus();
    });
    if (root && root.MutationObserver) {
      new root.MutationObserver(applyFilter).observe(tbody, {
        childList: true, subtree: true, characterData: true
      });
    }
    filter.hidden = false;
    applyFilter();
    return true;
  }
  function matchesIncident(text, priority, query, selected) {
    return (!selected || priority === selected) && String(text).toLowerCase().includes(String(query).trim().toLowerCase());
  }
  function mountIncidents(doc) {
    const controls = doc.getElementById("incident-filters");
    const catalogue = doc.getElementById("incident-catalogue");
    const search = doc.getElementById("incident-search");
    const severity = doc.getElementById("incident-severity");
    const reset = doc.getElementById("incident-reset");
    const count = doc.getElementById("incident-count");
    if (!controls || !catalogue || !search || !severity || !reset || !count) return false;
    if (mounted.has(controls)) return true;
    mounted.add(controls);
    const cards = Array.from(catalogue.querySelectorAll("[data-demo-priority]"));
    function apply() {
      let visible = 0;
      for (const card of cards) {
        card.hidden = !matchesIncident(card.textContent, card.dataset.demoPriority, search.value, severity.value);
        if (!card.hidden) visible++;
      }
      count.textContent = visible + " / " + cards.length + " scénarios DEMO" + (visible ? "" : " — aucun résultat");
    }
    search.addEventListener("input", apply);
    severity.addEventListener("change", apply);
    reset.addEventListener("click", () => { search.value = ""; severity.value = ""; apply(); search.focus(); });
    controls.hidden = false;
    apply();
    return true;
  }
  function mountAll(doc) { mount(doc); mountIncidents(doc); }
  if (typeof module !== "undefined" && module.exports) module.exports = { mount, mountIncidents, matchesIncident };
  if (root && root.document) {
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", () => mountAll(root.document), { once: true });
    } else mountAll(root.document);
  }
}(typeof window !== "undefined" ? window : null));
