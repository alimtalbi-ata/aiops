# STAR — Rendu Playwright des captures de test isolées

## Objectif
`demo/star_offline_chromium_fixture.py` constitue un premier exécutant Chromium réel, **uniquement pour des pages HTML de test locales**. Il accepte les tâches `star-browser-capture-tasks-v1` et une correspondance stricte `cue → nom_fichier.html` dans un répertoire explicitement fourni.

## Sécurité
- Aucun accès à GLPI, n8n, Grafana ni au portail Debian ; les pages sont injectées avec `page.set_content`.
- Le navigateur Chromium bloque les service workers, refuse les téléchargements et **abandonne toutes les requêtes réseau** avec `context.route('**/*', abort)`.
- Les noms de fichiers sont de simples basenames, sans traversées ni symlinks ; fichiers HTML limités à 256 Ko ; sorties créées dans un nouveau répertoire.
- Les PNG réels produits par Chromium dans ce mode sont **des images de fixtures synthétiques**, toujours étiquetées `SYNTHETIC_LOCAL_FIXTURE` avec SHA-256. Ils ne sont jamais des preuves des applications réelles. `runtime_proof_count=0`.
- Dépendance optionnelle : Python Playwright et navigateur Chromium installés dans un environnement isolé. Le module ne les installe pas et ne les déclenche pas lors de l'import.

## Contrôle de qualification
`tests/test_star_offline_chromium_fixture.py` valide les entrées sans lancer le navigateur (fixture admise, traversée interdite, déclaration de preuve falsifiée, fixture absente). Le workflow `STAR screenshot integrity collector` exécute ces tests. **Cette CI seule ne qualifie pas le rendu Chromium complet : un test navigateur explicite et ses artefacts sont encore nécessaires.**

## Suite
Construire une campagne navigateur indépendante avec fixtures Chromium réelles et qualification PNG/manifestes, puis seulement examiner les véritables routes métiers en lecture seule avec approbation et accès dédiés. Préserver la production Debian.
