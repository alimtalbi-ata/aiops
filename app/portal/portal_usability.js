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
  function selectableRunId(value) {
    return typeof value === "string" && /^RUN-[A-Za-z0-9][A-Za-z0-9_.-]{1,91}$/.test(value);
  }
  function mountRunSelection(doc) {
    const rows = doc.getElementById("portal-runs");
    const input = doc.getElementById("run-detail-id");
    const status = doc.getElementById("run-selection-status");
    if (!rows || !input || !status || mounted.has(rows)) return false;
    mounted.add(rows);
    let selectedRow = null;
    let selectedId = null;
    const originalId = row => row.cells[0]?.childNodes === undefined ? row.cells[0]?.textContent : Array.from(row.cells[0].childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('');
    function sync() {
      if (selectedRow && (!rows.contains(selectedRow) || originalId(selectedRow) !== selectedId)) {
        input.value = "";
        selectedRow = null;
        selectedId = null;
        status.textContent = "UNKNOWN — inventaire remplacé ; sélection effacée.";
      }
      for (const row of Array.from(rows.rows)) {
        if (row.cells.length !== 5) continue;
        const cell = row.cells[0];
        const existing = cell.querySelector("button[data-run-select]");
        const id = originalId(row);
        if (existing && existing.getAttribute("data-run-select") === id) continue;
        if (existing) existing.remove();
        if (!selectableRunId(id)) continue;
        const button = doc.createElement("button");
        button.type = "button";
        button.setAttribute("data-run-select", id);
        button.textContent = "Sélectionner";
        button.setAttribute("aria-label", "Sélectionner " + id + " pour une lecture autorisée");
        button.addEventListener("click", () => {
          if (!rows.contains(row) || row.hidden || originalId(row) !== id) return;
          selectedRow = row;
          selectedId = id;
          input.value = id;
          status.textContent = "Run sélectionné — authentification et ACL toujours requises.";
          input.focus();
        });
        cell.appendChild(button);
      }
    }
    input.addEventListener("input", () => { selectedRow = null; selectedId = null; status.textContent = "UNKNOWN — identifiant saisi manuellement ; ACL requise."; });
    if (root && root.MutationObserver) new root.MutationObserver(sync).observe(rows, {childList:true,subtree:true,characterData:true});
    sync();
    return true;
  }
  function mountAll(doc) { mount(doc); mountIncidents(doc); mountRunSelection(doc); }
  if (typeof module !== "undefined" && module.exports) module.exports = { mount, mountIncidents, matchesIncident, selectableRunId, mountRunSelection };
  if (root && root.document) {
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", () => mountAll(root.document), { once: true });
    } else mountAll(root.document);
  }
}(typeof window !== "undefined" ? window : null));
