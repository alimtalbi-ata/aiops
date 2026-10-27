# V2.13.54 — Plans de captures STAR F20.13 / V1, sans contact runtime

**Statut : composant de développement isolé, non déployé, pas une preuve métier.**

## Contexte historique et déduplication

Les journaux F20.13 des 15–16 octobre 2026 décrivent des captures Playwright du portail UCP, GLPI V1 `:8080`, n8n `:5678` et Grafana `:3000`. Ils contiennent des commandes/heredocs partiellement tronqués. Le passage Grafana `/login` n'est **pas** une preuve de dashboard incident. Les scripts originaux complets F20.13 ne sont pas disponibles dans le présent lot. Ils ne sont donc ni importés ni déclarés restaurés.

Ce changement réutilise **sans modification** `demo/star_snapshot_browser.py` (`CapturePlan`, `validate_plan`, `capture`) et les neuf cues de `demo/star_snapshot_choreography.py`. Il fournit uniquement l'assemblage déterministe et strict des **plans** à partir d'identités fournies indépendamment par Core et les applications. Il ne génère ni run_id, ni ID d'exécution, ni ticket, ni état observé.

Référence locale de qualification (candidat historique **et non** checkout GitHub complet) : archive `AIOps-V21346-Historical-Replay-Recovery-Cumulative-Offline-20261023.zip`, SHA256 `bc6f8e11018602d6ec752c3fdad5c0e149ca9cab186f4054c368816f8ede5bc3`, fichier `demo/star_snapshot_browser.py`, SHA256 `f2030c23d2a2adf4bd14c15af14a4e3491ccc5512819c1bd6efddeb4a256650f`. **Ne pas confondre ces octets avec la révision actuelle du dépôt.**

## Contrat HLD/LLD

`build_star_capture_plans(spec)` exige un `run_id` canonique, un `correlation_id` indépendant, les trois origines locales explicites, et **exactement neuf** checkpoints. Chaque checkpoint contient `event_ref`, `route` et sélecteurs DOM vérifiés par un opérateur (`run`, `correlation`, `event`, `state`, `redact`). Les identités absentes, réutilisations ambiguës des IDs d'exécution n8n, routes GLPI non numériques, mauvais ports, origine distante et fenêtres Grafana non fixes sont refusés.

| Checkpoints | Vue attendue | Identifiant de page | Route locale générée |
|---|---|---|---|
| detect, verify | Grafana | UID dashboard + fenêtre temporelle fixe et var-run_id | `:3000/d/{uid}/{slug}?from=…&to=…&var-run_id=…` |
| correlate, enrich, analyze, simulate | n8n | ID exécution + ID workflow | `:5678/workflow/{workflow_id}/executions/{execution_id}` |
| ticket, approve, close | GLPI V1 | ID ticket numérique | `:8080/front/ticket.form.php?id={ticket_id}` |

**Important :** ces URL sont des *candidats* à vérifier sur la version effective des applications. Une page de login, une erreur 200, un écran sans ID canonique visible, une absence de masque ou une contradiction de statut doivent échouer dans `capture`. L'approbation HITL et la clôture métier ne sont jamais inférées d'un texte affiché. L'origine réelle, l'authentification, la provenance et le lien temporel événement/capture exigent les contrôles distincts `star_browser_manifest_gate`, `star_event_capture_alignment` et `star_event_source_binding`.

Le constructeur ne fait **aucune** requête réseau. `capture(..., approved_read=False)` reste dry-run. La CI utilise `AIOPS_STAR_NO_RUNTIME=1` et, pour son seul test Chromium, `page.set_content` avec HTML synthétique, sans HTTP. Aucune capture synthétique ne doit être publiée comme preuve réelle.

## Interfaces et dépendances

Entrée : mapping Python local, valeurs strictement validées. Sortie : neuf objets `CapturePlan` ordonnés, aucune écriture. Dépendances : Python 3.12, modules STAR existants ; Playwright 1.57.0 + Chromium **uniquement** pour test navigateur isolé. Aucun accès Temporal, DGX, n8n, GLPI, Grafana, CMDB ou Docker.

## Qualification et limites

Tests unitaires : plans pour neuf scènes, ports V1, refus d'absence/contradiction, réutilisation d'exécution, fenêtre Grafana, ticket GLPI, masque obligatoire, dry-run et Chromium synthétique. La présence des sélecteurs DOM réels, la connexion aux applications, le parcours E2E sur `:17777`, l'origine indépendante des identifiants et les captures runtime sont **non qualifiés**.

## Retour arrière

Supprimer les trois nouveaux fichiers `demo/star_checkpoint_plan_builder.py`, `tests/test_star_checkpoint_plan_builder.py`, `.github/workflows/star-checkpoint-plan-builder-offline.yml` et cette note documentaire depuis la branche de PR uniquement. Aucune donnée de production, port, conteneur, ticket ou base n'a été modifié par ce composant.
