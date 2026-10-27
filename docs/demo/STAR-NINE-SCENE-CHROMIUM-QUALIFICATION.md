# STAR — Qualification de neuf scènes par Chromium isolé

## Contexte
Le test Chromium précédent ne couvrait qu'une seule fixture (`detect`). Le nouveau test `tests/test_star_offline_chromium_nine_scenes.py` parcourt les neuf jalons définis par `demo.star_snapshot_choreography.CUES` : detect, correlate, enrich, analyze, ticket, approve, simulate, verify, close.

## Fonctionnement
Chaque scène reçoit une page HTML **synthétique locale**, marquée `TEST FIXTURE ONLY`, sans accès aux interfaces réelles. Le module de rendu lance Chromium avec blocage des accès réseau, génère neuf fichiers PNG et un manifeste de captures. Le test recalcule pour chacun son SHA-256 et valide la structure PNG et ses CRC via `inspect_png`. Il vérifie également l'ordre des scènes et les marqueurs explicites `SYNTHETIC_LOCAL_FIXTURE`, `runtime_authenticated=false` et `business_state_verified=false`.

## CI
Le workflow `.github/workflows/star-offline-chromium-real-render.yml` installe Playwright et Chromium dans le runner GitHub puis exécute les tests de rendu à une et neuf scènes. Ce sont des tests de navigateur réels contre **fixtures locales uniquement**. Le succès de cette CI ne démontre pas que les URL métiers, sessions et données GLPI/n8n/Grafana ou l'interface Debian sur `:17777` fonctionnent.

## Suite
La prochaine qualification nécessite un environnement applicatif isolé reproduisant les pages et les événements, suivi d'un rattachement attesté run_id ↔ exécution n8n ↔ ticket GLPI ↔ alerte Grafana. Conserver le mode de remédiation simulée et ne pas modifier la production Debian.
