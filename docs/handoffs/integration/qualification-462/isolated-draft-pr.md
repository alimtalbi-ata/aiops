Cette candidate réutilise le socle #194 pour qualifier les vrais services Core→Temporal→Worker dans un banc Cloud isolé. L'incrément Core conserve un reçu durable après progression du Run et refuse les dispatchs LIVE ou les réponses Worker incohérentes. Aucun arbre récent n'est importé globalement.

Référence de coordination : #462. **DRAFT uniquement, aucune fusion ni promotion Debian. Agent 7 rédacteur unique ; Core/Worker en revue (revues non encore obtenues).**

## Base et périmètre exact

- Base cible : `feat/temporal-hitl-v1`, vérifiée à `40d38705cf2bde3be6052340442c117a81908f65` (#194), et non main. Vérifier qu'elle n'a pas avancé avant création ; arrêter et documenter si elle a changé.
- Head : `agent/integration/462-isolated-candidate`. La référence exacte à examiner est fournie dans le paquet local de publication ; ne pas reprendre un autre HEAD.
- `app/core/main.py` : seule fonction `execute`, adaptée de #474 `c13d56acf050126e65fae120ac8d2f7f1abd5a3f` (protections #470/#472/#474).
- `tests/test_candidate_core_execute.py` : sept régressions réutilisées ; fixture RequestException corrigée.
- `tools/qualification/bench462.py` et `bench462.Dockerfile` : sources exportées au commit exact, image contrôlée, services natifs #194, ressources privées labellisées, aucun port publié, reçu et replay.
- `docs/handoffs/integration/qualification-462/isolated-*`, `bench462-*` : attribution, provenance, reçus, historiques, logs, tests et empreintes.
- `.github/workflows/quality.yml` : ajout de la seule branche candidate au trigger push et des sept tests Core ; aucun contrôle existant supprimé. Cette exception au gel CI est consignée dans le registre.

63 des 64 fichiers applicatifs sont byte-identiques à #194 ; AST Core identique hors execute. Worker/workflow, OIDC HITL, outbox, Policy, Evidence, Intelligence, registres IA, migrations et configurations de production sont préservés. Les chemins réservés #454/#453 et le producteur Integration restent en lecture seule. #466/action-bound reste différé.

## Preuves réellement obtenues

- 47 tests ciblés PASS : identité 11, contrat HITL 9, Intelligence 16, Critic 4, Core execute 7. Un premier échec de chemin de fixture HITL et son rerun restent joints.
- Banc `aiops2-agent7-462-3f5f6820` : neuf conteneurs actifs sans restart ni port publié au snapshot ; contrôle prolongé 98 secondes.
- Run `RUN-03A3F5BF7578B5ED`, Temporal `01a1c21b-b8f1-7a26-bed0-4ddd9814e1b8` : Core RESOLVED, Temporal COMPLETED ; 95 événements, replay SDK PASS.
- Trois execute supplémentaires : même reçu durable, une ligne en DB, même Temporal Run ID, historique inchangé ; un POST Worker avant/après, donc aucun second dispatch observé.
- Policy PASS/SIMULATE ; HITL DEMO synthétique sans autorité d'effet, zéro approbation et zéro ligne d'outbox ; token interne refusé comme identité humaine (503, IdP non configuré).
- Deux échecs Temporal dev conservés. Version 1.4.1 épinglée ; le changement de version seul ne suffisait pas. Correction de routage des seuls appels locaux 0.0.0.0 hors proxy ; ni scanner ni garde désactivés.
- Image applicative `sha256:4d4720c1caa132ed62c98dc9133dfd8ecd6bc1abc6d6ebe1ae4e9bcfa74f1818` ; manifeste source `49b98b4840c2db6a74318a773e1fbffe6062345507dc7f38b8f602c37c0bd8a3`.

Handoff : `docs/handoffs/integration/qualification-462/isolated-bench-handoff.md`. Reçu stable : `bench462-stable-receipt.json`. Intégrité : `bench462-SHA256SUMS`.

## CI à vérifier au HEAD exact

Le push de la candidate déclenche `AIOps quality gates` avec checkout du SHA de l'événement push. Relever URL, event, head_sha, checkouts et conclusion de tous les jobs. La CI de PR peut tester un merge synthétique : ne pas la substituer à cette vérification. La nouvelle étape Core utilise les sept tests ciblés ; les jobs existants restent présents.

À la préparation : **CI UNKNOWN**, aucun résultat Actions revendiqué ; API GitHub bloquée par CONNECT 403. Le résultat local et le résultat du futur run CI sont des preuves distinctes. Si une PR existe déjà pour ce head, réutiliser son numéro, ne pas créer de doublon.

## Limites et risques

Fournisseur de test déterministe existant, explicitement synthétique ; pas de modèle réel ni de GLPI authentifié. Ni navigateur ni approbation OIDC réelle qualifiés. La durée observée ne prouve pas la disponibilité de production. Le socle #194 n'embarque pas toutes les corrections ultérieures : les ports suivants nécessitent provenance et tests indépendants, sans copie d'arbres.

**Debian, FS1250 et E2E réels HOLD.** Aucun déploiement, merge, écriture GLPI/PG de production, modification cron ou contournement Policy/HITL. Retrait de la candidate = cesser son utilisation et conserver les preuves ; aucun rollback Debian requis. Toute correction doit suivre une reproduction et un commit distinct.
