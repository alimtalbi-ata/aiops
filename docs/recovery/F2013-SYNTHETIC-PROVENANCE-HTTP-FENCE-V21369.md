# F20.13 → STAR — verrouillage de provenance synthétique (V2.13.69)

Date : 2026-10-24. Portée : dépôt GitHub et qualification isolée uniquement.
Statut : correction de contrat publiée ; **aucune attestation E2E de la production Debian**.

## Source et traçabilité

- Origine historique : `AIOps-UCP-F20.13-DEMO-MULTISTACK-KIT-v0.3`, membre `AIOps-UCP-F20.13-DEMO-MULTISTACK-KIT-v0.3/scripts/capture-multistack.py`.
- SHA-256 de l'archive originale : `cc2fdc0f1d7b2b3e82937925030d7dbb978fe341f4ed2d74030e59462a7190f1`.
- SHA-256 du membre historique : `bc8fb46e81d37cb90f64d53feaa7e14171aa65e0137a0143650ba04d12e623ee` ; taille 3 928 octets.
- Ces valeurs proviennent de l'inventaire privé `AIOps-V21365-F2013-Original-ZIP-SHA256-Metadata-Only.json`, déjà contrôlé. L'archive originale n'a **pas** été réouverte pendant ce changement ; aucune preuve ni code brut privé n'est publié ici.
- Source moderne comparée : `demo/star_snapshot_browser.py` sur la branche de PR #36. L'ancien collecteur reste en quarantaine ; pas de recopie ni de déploiement.

## Besoin métier et défaut corrigé

La campagne F20.13 a montré qu'un succès de capture peut ne représenter qu'une page de connexion.
Pour STAR, les neuf checkpoints GLPI/n8n/Grafana doivent distinguer une fixture locale
synthétique d'une navigation opérateur HTTP réelle. Jusqu'à cette correction, un plan
`ISOLATED_TEST_FIXTURE` exécuté avec `approved_read=True`, sans `fixture_html`,
pouvait tomber dans la branche de navigation HTTP si `AIOPS_STAR_ALLOW_OPERATOR_READ=1`.
Cela risquait de produire une capture **mal étiquetée synthétique**, ensuite rejetée
par le validateur de manifestes, mais seulement *après* un accès réseau.

## Architecture et interfaces

`capture(CapturePlan, output_dir, approved_read, fixture_html)` vérifie maintenant,
**avant tout import Playwright, lancement Chromium ou accès HTTP**, que
`environment=ISOLATED_TEST_FIXTURE` et `approved_read=True` imposent
`fixture_html is not None`. Les dry-runs restent sans effet.
La provenance `OPERATOR_BROWSER_UNREVIEWED` demeure un mode distinct,
nécessitant une autorisation explicite et les protections de requêtes GET.
Le manifeste synthétique doit toujours annoncer
`LOCAL_HTML_FIXTURE_NO_HTTP`, sans prétendre à une authentification runtime.

Dépendances : `demo/star_snapshot_choreography.py`,
`demo/star_browser_request_fence.py`, Playwright/Chromium seulement pour
les captures explicitement autorisées ; aucune dépendance réseau pour le test
de refus. Le contrat de sortie conserve `runtime_authenticated=False` et
n'autorise jamais de remédiation LIVE.

## Qualification et conditions de réutilisation

- Test de régression ajouté : `tests/test_star_snapshot_browser_hardening.py::BrowserHardeningTests.test_isolated_provenance_cannot_browse_runtime_even_with_operator_opt_in`.
- Données synthétiques, répertoire temporaire, opt-in opérateur simulé, **aucun accès au runtime**.
- Résultat attendu : `ValueError` avant ouverture du navigateur, aucun fichier écrit.
- Le contrôle Chromium complet, les neuf checkpoints authentifiés, l'identité
  02→03 et le portail Debian `:17777` restent des qualifications indépendantes.
- Réutilisation historique autorisée seulement après comparaison SHA, revue des
  dépendances, nettoyage des données privées, tests isolés et décision explicite.

## Rollback

Revenir uniquement sur le commit du correctif de `demo/star_snapshot_browser.py`
et sur son test associé dans la branche de PR, après revue. Ne jamais modifier
`main`, la production Debian, les conteneurs V1/containerd, ni les applications
GLPI/n8n/Grafana/DB/CMDB. La suppression du garde-fou réintroduirait la
confusion de provenance : **rollback déconseillé sans contrôle équivalent**.
