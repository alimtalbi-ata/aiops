# AIOps NOC — Lot de preuves STAR déterministe, hors ligne

`demo/noc_star_trace_bundle.py` produit neuf événements STAR synthétiques dans l'ordre canonique (detect, correlate, enrich, analyze, ticket, approve, simulate, verify, close). Tous portent un `run_id` et un `incident_id` de démonstration constants, des identifiants événement uniques et `source_type=SYNTHETIC`.

À partir d'un index de captures NOC préalablement classé `OFFLINE_TEST`, le module fabrique trois livrables : `star-events.json` (événements déterministes), `star-event-binding.json` (empreintes SHA-256 et correspondances illustratives), `star-trace.html` (consultation des neuf étapes et des trois captures). Les fichiers sont créés sans écraser des sorties existantes.

Le workflow Chromium qualifie désormais le module avec `tests/test_noc_star_trace_bundle.py`, puis génère les trois fichiers dans l'artefact de preuves NOC, après validation des captures, de l'index et du centre de preuves.

**Périmètre et interdictions :** source synthétique, zéro lien événement/runtime validé et aucune preuve d'origine réelle. Les fichiers ne doivent jamais être présentés comme captures authentifiées de Checkmk, Thruk, GLPI, n8n, Grafana ou du portail Debian. Le contrôle CI du commit final reste indispensable avant qualification.
