# #462 — référence commune et attribution du banc isolé

Base applicative gelée : **PR #194, `40d38705cf2bde3be6052340442c117a81908f65`**. Branche candidate : `agent/integration/462-isolated-candidate`. Ce commit ne modifie aucune source applicative ; il est publié avant le premier incrément et avant démarrage des services.

**Rédacteur unique : Agent 7 sur cette candidate uniquement.** Core #458 et Worker #459 interviennent en revue ; aucun agent n’est prétendu lancé ou avoir approuvé une revue. Leurs branches sont préservées. Aucun rédacteur concurrent sur les mêmes chemins.

| Fichiers | Rédacteur | Revue / limites |
| --- | --- | --- |
| `app/core/main.py` | Agent 7 | Core et Worker ; seule fonction execute pour adapter #470/#472/#474, sans perdre les autres routes #194 |
| `app/worker/main.py`, `app/worker/workflow.py` | Agent 7 | Worker/Core ; gel initial, patch seulement sur problème reproduit et dans un incrément distinct ; garder signal HITL et garde LIVE |
| `app/core/action_bound_admission.py`, son test | Agent 7 pour port futur | Core #466 ; différé, ELIGIBLE ne vaut jamais autorisation LIVE |
| `tools/qualification/bench462.py`, `bench462.Dockerfile` | Agent 7 | Integration/Core/Worker ; harness isolé, pas nouvel exemple produit |
| `tests/test_candidate_core_execute.py` | Agent 7 | Core/Worker ; réutiliser la suite #474 et corriger seulement son faux type RequestException |
| `docs/handoffs/integration/qualification-462/isolated-*`, `bench462-*` | Agent 7 | Manifestes, incréments et preuves de ce banc |

Les chemins gelés sont exhaustivement listés dans `isolated-candidate-base.json` : Policy, shared, Evidence, Intelligence, HITL/denial Core, test provider, Twin/Portal, migrations et configuration de production. Les fichiers réservés #454/#453 et le producteur Integration restent en lecture seule. Aucun changement Debian, GLPI ou PostgreSQL de production. Les nouvelles configurations du banc sont générées hors des checkouts et utilisent un projet Docker unique.

Le premier objectif utilise les vrais services #194 et le SDK Temporal. Le fournisseur déterministe **déjà existant** peut servir au Run DEMO, avec provenance explicitement synthétique ; cela ne qualifie pas une inférence de modèle réel. HITL DEMO ne crée ni approbation native ni autorité d’effet. Les capacités OIDC/outbox et les registres IA sont conservés ; GLPI authentifié et navigateur sont différés.

Chaque incrément conserve SHA source, delta, tests et manifeste. Pas de merge global des arbres récents. Rejeu du même Run attendu sans second dispatch et replay SDK de l’historique isolé. Debian, FS1250 et E2E réels restent HOLD.

Git HTTPS permet la publication de cette référence. L’API GitHub reste refusée par le proxy (CONNECT 403) ; aucune création de PR ni commentaire d’issue n’est prétendu effectué par Codex. La branche d’intégration précédente et ses modifications distantes sont laissées intactes.

## Exception CI demandée après qualification locale

Agent 7 reste seul rédacteur de `.github/workflows/quality.yml` sur cette candidate : ajout du déclencheur push pour cette seule branche et des sept tests Core existants. Tous les jobs et permissions existants sont conservés. Cette exception précise au gel initial `.github/**` répond à la demande de PR DRAFT et de CI sur son HEAD. Sur push, checkout utilise le SHA de cet événement ; les checks pull_request peuvent porter sur un commit de merge synthétique, à distinguer du HEAD.
