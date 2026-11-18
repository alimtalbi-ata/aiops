/* Portal usability layer: progressive enhancement only; no API calls or stored state. */
(function (root) {
  "use strict";

  function element(doc, tag, className, text) {
    const node = doc.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function link(doc, href, label, description) {
    const a = element(doc, "a", "portal-quick-link");
    a.href = href;
    const title = element(doc, "strong", "", label);
    const hint = element(doc, "span", "", description);
    a.appendChild(title);
    a.appendChild(hint);
    return a;
  }

  function mount(doc) {
    const main = doc.querySelector("main");
    if (!main) return false;
    main.id = main.id || "portal-main";

    const headerNav = doc.querySelector("header nav");
    if (headerNav) headerNav.setAttribute("aria-label", "Navigation principale");

    if (!doc.getElementById("portal-skip-link")) {
      const skip = element(doc, "a", "portal-skip-link", "Aller au contenu principal");
      skip.id = "portal-skip-link";
      skip.href = "#" + main.id;
      main.setAttribute("tabindex", "-1");
      doc.body.insertBefore(skip, doc.body.firstChild || null);
    }

    if (!doc.getElementById("portal-workspace-nav")) {
      const nav = element(doc, "nav", "portal-workspace-nav");
      nav.id = "portal-workspace-nav";
      nav.setAttribute("aria-label", "Accès rapide");
      [
        ["#runs", "Runs"], ["#noc", "Supervision NOC"],
        ["#twin", "Digital Twin"],
        ["/itsm", "GLPI / ITSM"], ["/demo/acme-impact", "Impact métier"],
        ["/demo/explore-story", "Explore / Story"]
      ].forEach(function (item) {
        const a = element(doc, "a", "", item[1]);
        a.href = item[0];
        nav.appendChild(a);
      });
      main.insertBefore(nav, main.firstChild || null);
    }

    if (!doc.getElementById("portal-quickstart")) {
      const hero = element(doc, "section", "portal-quickstart");
      hero.id = "portal-quickstart";
      const heading = element(doc, "div", "portal-quickstart-copy");
      heading.appendChild(element(doc, "p", "portal-eyebrow", "AIOPS 2.0 · OPERATIONS"));
      heading.appendChild(element(doc, "h2", "", "Votre espace de pilotage"));
      heading.appendChild(element(doc, "p", "portal-quickstart-note",
        "Accédez directement aux opérations, à la supervision et aux outils. Les données non qualifiées restent UNKNOWN."));
      hero.appendChild(heading);
      const actions = element(doc, "div", "portal-quickstart-actions");
      actions.appendChild(link(doc, "#runs", "Consulter les Runs", "Activité et exécutions"));
      actions.appendChild(link(doc, "#noc", "Ouvrir la supervision", "NOC et observabilité"));
      actions.appendChild(link(doc, "/itsm", "Espace ITSM", "GLPI et parcours opérateur"));
      actions.appendChild(link(doc, "/demo/acme-impact", "Impact métier", "Scénario explicitement simulé"));
      hero.appendChild(actions);
      const firstHeading = main.querySelector("h1");
      if (firstHeading && firstHeading.parentNode === main) {
        main.insertBefore(hero, firstHeading.nextSibling);
      } else {
        main.insertBefore(hero, main.children[1] || null);
      }
    }

    const runs = doc.getElementById("runs");
    if (runs && !doc.getElementById("portal-run-filter")) {
      const filter = element(doc, "div", "portal-run-filter");
      const label = element(doc, "label", "", "Filtrer les Runs affichés");
      label.htmlFor = "portal-run-filter-input";
      const input = element(doc, "input");
      input.id = "portal-run-filter-input";
      input.type = "search";
      input.placeholder = "Rechercher un ID, statut, mode ou scénario…";
      input.setAttribute("autocomplete", "off");
      const result = element(doc, "span", "portal-filter-result", "Filtre local · aucune donnée supplémentaire chargée");
      result.id = "portal-run-filter";
      filter.appendChild(label);
      filter.appendChild(input);
      filter.appendChild(result);
      runs.parentNode.insertBefore(filter, runs);
      result.setAttribute("aria-live", "polite");
      const applyFilter = function () {
        const query = input.value.trim().toLowerCase();
        const rows = runs.querySelectorAll("tbody tr");
        let visible = 0;
        rows.forEach(function (row) {
          const match = !query || row.textContent.toLowerCase().includes(query);
          row.hidden = !match;
          if (match) visible += 1;
        });
        result.textContent = query
          ? visible + " ligne(s) correspondante(s) · filtre local uniquement"
          : "Filtre local · aucune donnée supplémentaire chargée";
      };
      input.addEventListener("input", applyFilter);
      if (root && root.MutationObserver) {
        const observer = new root.MutationObserver(applyFilter);
        observer.observe(runs, { childList: true, subtree: true, characterData: true });
      }
      const table = runs.querySelector("table");
      if (table) table.setAttribute("aria-label", "Runs canoniques — données non attestées tant que la source reste UNKNOWN");
    }

    ["portal-read-result", "run-detail-error", "portal-navigation-status",
      "noc-result", "noc-grafana-result", "noc-rag-result", "a", "demo"].forEach(function (id) {
      const node = doc.getElementById(id);
      if (node) node.setAttribute("aria-live", "polite");
    });

    return true;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { mount };
  if (root && root.document) {
    if (root.document.readyState === "loading") {
      root.document.addEventListener("DOMContentLoaded", function () { mount(root.document); }, { once: true });
    } else {
      mount(root.document);
    }
  }
}(typeof window !== "undefined" ? window : null));
