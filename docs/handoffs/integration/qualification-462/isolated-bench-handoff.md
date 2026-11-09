# Agent 7 — banc candidat #462 sur socle #194

## Référence commune publiée avant démarrage

Branche : `agent/integration/462-isolated-candidate`. Commit de base commune et attribution : **`c771e41e5e2fbf11ea97bb8662cb94ddff297a34`**, parent applicatif **#194 `40d38705cf2bde3be6052340442c117a81908f65`**. Agent 7 est rédacteur unique sur cette candidate ; Core/Worker sont désignés en revue, sans prétendre qu’une revue ait déjà eu lieu. Les branches de composants et la branche #462 précédente, modifiée à distance, ont été préservées. Voir `isolated-candidate-base.json` et `.md`.

## Incréments et provenance

1. **`291fe0ce8c931429c5f57a8cc46d797b67daac77`** : adaptation de la seule fonction `Core.execute` à partir de #474 `c13d56acf050126e65fae120ac8d2f7f1abd5a3f`, qui porte les protections #470/#472/#474. Sept tests Core PASS ; seul ajustement de fixture = véritable classe RequestException pour le faux client HTTP. Aucun autre symbole Core modifié.
2. **`8fced9821c0cd2419105cd3209c058862e400177`** : harness de qualification `tools/qualification/bench462.py` et Dockerfile de banc. Réemploi des gardes de ressources, isolation de projet, SHA source et contrôle d’image du runner #468. Les services sont les vraies entrées #194, pas le runtime minimal #468.

La vérification de préservation compare les 64 fichiers applicatifs à #194 : **63 fichiers byte-identiques**, seul `app/core/main.py` diffère ; AST identique hors fonction execute. La paire Worker/workflow, les registres IA, l’outbox, le HITL OIDC, Intelligence, Policy, Evidence et shared sont inchangés. Tous les fichiers de migration #194, y compris les seeds synthétiques nécessaires au scénario DEMO existant, ont été exécutés uniquement dans le PostgreSQL jetable de ce banc. Aucun de ces seeds ne vaut signal FS1250 réel.

## Services réellement démarrés

Projet Docker local **`aiops2-agent7-462-eb1af91f`**, neuf conteneurs : PostgreSQL, Temporal dev, Core, Worker, Policy, Evidence, Intelligence, Twin et fournisseur de test déterministe déjà présent dans #194. Pendant le Run, les sept services disposant d’un healthcheck étaient healthy ; Temporal et le fournisseur ont répondu fonctionnellement. **Après le premier résultat, Temporal a terminé sur une panique SDK/scanner vers 60 secondes : le maintien en service du banc est BLOCKED à ce stade.** Voir `bench462-initial-stability.json` et le log de panique conservé. Une correction séparée de la dépendance Temporal du banc et une nouvelle qualification sont nécessaires. Réseau interne, **aucun port publié**. Aucun conteneur ni volume des autres projets n’a été touché ; les ressources propres du banc sont laissées actives pour revue.

Image applicative immuable exécutée : **`sha256:4d4720c1caa132ed62c98dc9133dfd8ecd6bc1abc6d6ebe1ae4e9bcfa74f1818`**. Révision source image : `8fced9821c0cd2419105cd3209c058862e400177`. Empreinte du manifeste de tous les fichiers applicatifs : **`49b98b4840c2db6a74318a773e1fbffe6062345507dc7f38b8f602c37c0bd8a3`**, vérifiée dans le conteneur avant qualification. Temporal utilise le digest exact référencé dans le harness ; IDs et digests observés sont consignés dans `bench462-runtime.json`.

Les secrets sont aléatoires et propres au banc, dans une configuration chmod 0600 hors checkout. Aucun secret/configuration de production copié. TLS et vérifications de téléchargement ont été conservés ; CA de session fournie par montage de build, pas copiée dans l’image.

## Premier objectif : PASS pour le DEMO isolé uniquement

- Run : **`RUN-D26145DBCD5542B4`** ; Incident : `INC-BENCH462-BF437AD56EF8`.
- Workflow ID : identique au Run ; Temporal Run ID : **`01a1c212-95df-724f-99bd-207facb83a7d`**.
- Core **RESOLVED** ; Temporal **COMPLETED** ; 13 stages d’exécution PASS, plus l’étape INGEST.
- Réels appels HTTP entre les services natifs, un registre Analyst, un registre Critic validé, un registre Policy ; **PASS/SIMULATE** relu dans Core.
- HITL DEMO : événement natif `HITL_SIMULATION_SKIPPED`, provenance synthétique et `execution_allowed=false` ; **zéro approbation et zéro ligne d’outbox HITL créées**. Le token interne ne peut pas autoriser une décision humaine OIDC : route présente, refus 503 car fournisseur OIDC non configuré. Les capacités natives sont préservées, pas qualifiées comme une approbation réelle.
- **Un reçu durable** en DB. Trois appels execute supplémentaires après progression retournent tous le même reçu idempotent et le même workflow.
- Historique Temporal **95 événements avant et après** ces appels ; même Temporal Run ID ; journal HTTP Worker : **un POST execution/start avant, un après**, donc aucun second dispatch observé.
- **Replay du véritable historique par le SDK Temporal PASS**, avec la classe de workflow #194 de l’image exécutée. L’historique est joint, pas un JSON de succès fabriqué.

## Tests et preuves conservés

Sept tests ciblés Core ont d’abord passé localement. Puis, dans l’image **Python 3.13**, les suites existantes/ciblées donnent : OIDC/identité 11 PASS, contrat HITL 9 PASS, Intelligence 16 PASS, Critic repair 4 PASS, Core execute 7 PASS : **47 tests PASS**. Les tests d’identité utilisent des clés/claims de fixtures : ils ne prouvent pas une connexion au vrai IdP.

Un premier essai du contrat HITL a donné 8 PASS et 1 erreur : le répertoire de migration n’avait pas été fourni au chemin attendu par la suite statique. Après copie des mêmes fichiers d’origine dans l’espace de tests du conteneur, rerun 9 PASS. L’échec initial et le rerun restent joints ; aucun code/contrat n’a été changé pour masquer l’échec. Les modifications d’environnement de ces tests concernent leurs processus exec séparés, pas les services.

Preuves : `bench462-receipt.json`, `bench462-run.json`, `bench462-ledger.json`, `bench462-history.json`, `bench462-source-manifest.json`, `bench462-preservation.json`, `bench462-runtime.json`, logs de suites et `bench462-services.log`. Empreintes dans `bench462-SHA256SUMS`. Les artefacts ont été vérifiés contre les secrets propres au banc avant publication. Le compose privé n’est pas dans Git.

## Reproduction

Sur une machine Cloud disposant de son Docker local, dans cette branche commitée :

```bash
python tools/qualification/bench462.py
```

Le harness refuse une source non commitée ou moins de 4 GiB libres, fixe le socket Docker local, crée un projet aléatoire labellisé, exporte les sources au SHA HEAD et vérifie le manifeste dans l’image. Il ne lance aucun script Debian, cron ou writer GLPI. Le même contenu applicatif peut réutiliser une image dont l’empreinte correspond. Un nouveau lancement crée son propre PostgreSQL/Temporal et son propre Run : ce n’est pas le test de rejeu du Run précédent, qui est effectué à l’intérieur de chaque qualification.

Les neuf conteneurs sont propres à ce banc. Le harness ne nettoie pas des ressources existantes ; si un arrêt devient nécessaire, identifier et arrêter uniquement ce projet exact après revue des labels. Le futur environnement doit réexécuter les contrôles ; le résultat actuel ne prouve pas sa restauration dans un autre Cloud.

## Limites et prochaine revue

**CODE/DEMO isolé : PASS au périmètre décrit ; CI de la candidate : UNKNOWN, aucun résultat Actions revendiqué.** Le fournisseur est celui de test **déterministe et explicitement synthétique** de #194 : pas une inférence d’un modèle réel. HITL DEMO ne qualifie ni l’authentification OIDC de production ni une approbation native, et ne confère aucune autorité de remédiation LIVE.

GLPI authentifié, navigateur, modèle réel et approbation OIDC réelle sont différés. **Debian, FS1250 et E2E réels restent HOLD.** Aucun remplacement Debian n’a été choisi à partir des checkouts modifiés ou d’une provenance inconnue. Aucun merge/PR créé, aucune écriture GLPI ou PostgreSQL de production, aucun réglage cron/Compose de production changé.

La base/attribution a été publiée par Git HTTPS avant les travaux. L’API GitHub reste bloquée par CONNECT 403 : aucun commentaire #462 n’est prétendu posté par Codex. Les preuves et ce handoff sont publiés dans la même branche candidate pour revue Core/Worker, sans écriture concurrente. Tout nouvel incrément devra conserver ces capacités et ce reçu de non-redispatch.
