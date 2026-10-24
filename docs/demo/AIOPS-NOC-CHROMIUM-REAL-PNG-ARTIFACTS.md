# AIOps — Captures Chromium vérifiables du NOC unifié

## Fonctionnalité
Le test d'intégration `tests/test_noc_unified_chromium.py` exécute Chromium sur une page HTML NOC produite hors ligne. Il vérifie le rendu du panneau ACME synthétique et de la vue Checkmk issue d'exports non authentifiés. Après vérification des deux panneaux, il enregistre trois PNG si `AIOPS_NOC_BROWSER_EVIDENCE_DIR` est défini : la vue unifiée, le panneau synthétique et le panneau Checkmk exporté.

Chaque fichier est contrôlé via `demo.star_png_integrity.inspect_png` (structure PNG et empreinte SHA-256). Le manifeste `aiops-noc-offline-browser-artifacts-v1` consigne le nom, la taille, l'empreinte et les mentions `LOCAL_OFFLINE_BROWSER_RENDER`, `runtime_authenticated=false`, `runtime_proof_count=0`.

## CI
`.github/workflows/star-offline-chromium-real-render.yml` installe Playwright, lance les tests navigateur sans réseau et publie `noc-offline-browser-evidence` avec `actions/upload-artifact@v4` (rétention 7 jours). Ce sont les fichiers effectivement produits par Chromium lors du test et non des images générées artificiellement en remplacement des captures. Vérifier l'exécution CI et l'existence des artefacts avant de les présenter comme qualifiés.

## Limites
Le jeu ACME et l'export Checkmk sont **des exemples de test**, pas la production ; les iframes sont isolées par sandbox, sans `allow-same-origin`. Aucune requête réseau n'est autorisée. Le portail Debian `:17777`, les conteneurs NOC historiques et les vrais workflows GLPI/n8n/Grafana ne sont ni contactés ni modifiés.

## Prochaine priorité
Importer ces preuves navigateur dans le centre de démonstration sous une catégorie `OFFLINE_TEST` non promouvable en preuve runtime. Puis qualifier la structure et la fraîcheur d'exports du véritable environnement de test Checkmk/Thruk, avant toute intégration au portail.
