# AIOps — Index de preuves NOC offline

`demo/noc_evidence_index.py` construit un index déterministe à partir des trois captures Chromium vérifiées (unified, synthetic et checkmk-export). Le module appelle le contrôle d'intégrité des fichiers PNG et du manifeste avant toute indexation.

L'index `aiops-noc-evidence-index-v1` contient les fichiers, leur empreinte SHA-256 et taille, leur origine `LOCAL_OFFLINE_BROWSER_RENDER`, et leur catégorie **OFFLINE_TEST**. Les compteurs `OBSERVATION` et `RUNTIME_EVIDENCE` restent à zéro. Chaque entrée porte `runtime_authenticated=false` et `promotable_to_runtime=false` ; aucune fonctionnalité ne permet de déclarer artificiellement une preuve authentifiée.

La CI Chromium génère désormais `evidence-index.json` après validation, dans l'artefact `noc-offline-browser-evidence`. Les tests contrôlent le classement de trois preuves hors ligne et le rejet des captures altérées. **La CI du dernier commit doit être contrôlée avant de qualifier cette livraison.**

Ce travail ne raccorde pas le portail :17777, Checkmk/Thruk de production, Grafana, n8n ou GLPI. Les états exportés restent non authentifiés et les scénarios ACME restent synthétiques.

Étape suivante : enrichir le centre de démonstration avec cet index en lecture seule, sans mélange des classes de preuves, puis concevoir le contrat d'ingestion d'observations réellement sourcées et horodatées.
