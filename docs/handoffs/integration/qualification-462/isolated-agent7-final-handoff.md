# Agent 7 — livraison finale expurgée Integration #462

Mission terminée. Livraison documentaire pour reprise de coordination nocturne par le CLI Debian ; elle n'autorise ni merge, ni déploiement, ni écriture de production. Aucun nouveau travail commencé après cette livraison. Agent 7 est resté rédacteur unique sur sa candidate ; aucune revue Core/Worker non obtenue n'est prétendue acquise.

## Références exactes

- Dépôt : alimtalbi-ata/aiops ; branche : `agent/integration/462-isolated-candidate`.
- Socle applicatif #194 : `40d38705cf2bde3be6052340442c117a81908f65` ; cible de PR préparée `feat/temporal-hitl-v1`, pas main. Aucune PR n'est prétendue créée par Codex.
- Référence de revue antérieure : `3f2e361c1997ff14a490bb240eea902820a1302f`.
- Parent avant correctif PostgreSQL : `e0fc66c3bc8f56cace0074de2f0a07d5bb551303`.
- **SHA examiné et qualifié en CI : `e7c76514b8e98cb35a9594226e7106fde98a42aa`.** La CI réussie ne couvre que ce SHA. Le commit qui ajoute le présent rapport et son instantané CI est documentaire, descendant de ce SHA ; son résultat CI éventuel ne doit pas être présumé.
- Correctifs séparés : `8011ddd6ff0130e52500a0832db187759a0e1025` (clients PostgreSQL16), puis `e7c76514b8e98cb35a9594226e7106fde98a42aa` (runner PostgreSQL Ubuntu24.04).

## Périmètre et préservation

Le seul changement applicatif par rapport à #194 est la fonction Core execute, adaptée des protections #470/#472/#474 avec provenance. 63 des64 fichiers applicatifs sont byte-identiques ; AST Core identique hors execute. Worker/workflow, Policy, HITL OIDC/outbox, Analyst/Critic, Evidence, Intelligence, registres IA et migrations sont conservés. Les attributions et gels sont dans `isolated-candidate-base.json` et `.md`. Les correctifs PostgreSQL depuis e0fc66c3 ne changent aucun fichier applicatif, migration ni outil de banc.

## Tests et preuves obtenus

- 47 tests ciblés locaux PASS : identité11, HITL9, Intelligence16, Critic4, Core7. L'échec initial de chemin de fixture HITL et son rerun sont conservés, sans changement de contrat.
- Banc Cloud natif isolé : neuf services observés running sans restart ni port publié ; 98secondes de contrôle incluant la qualification. Run `RUN-03A3F5BF7578B5ED`, Temporal `01a1c21b-b8f1-7a26-bed0-4ddd9814e1b8` : Core RESOLVED, Temporal COMPLETED ;95 événements, replay SDK PASS.
- Reçu durable en DB ; trois execute supplémentaires retournent le même reçu, même Temporal Run ID, même historique et une seule ligne de reçu ; un seul POST Worker avant/après, aucun second dispatch observé.
- Policy PASS/SIMULATE ; HITL DEMO explicitement synthétique, sans autorité d'effet, zéro approbation et zéro ligne d'outbox. Refus du token interne comme identité humaine,503 car IdP non configuré. Aucune approbation OIDC réelle revendiquée.
- PostgreSQL jetable : pg_dump, pg_restore, psql16.15, chemins versionnés `/usr/lib/postgresql/16/bin/`; serveur16.15, BINDIR déclaré identique. Restauration32 tables PASS, empreintes MATCH, archive corrompue rejetée. Corps antérieur de restauration/intégrité byte-identique après le précontrôle ajouté ; aucune commande SQL filtrée.
- Commandes principales : `bash -n tests/postgres-dr-rehearsal.sh`, `git diff --check`, sept tests via `python -m unittest discover -s tests -p test_candidate_core_execute.py -v`, test DR réel via bash dans un conteneur jetable avec `DR_POSTGRES_BINDIR=/usr/lib/postgresql/16/bin`, et contrôle négatif psql `SET transaction_timeout = 0` (refus attendu).

Preuves publiées dans ce répertoire : `bench462-stable-*`, `bench462-preservation.json`, logs des suites, `bench462-postgres16-*`, `bench462-SHA256SUMS`, `isolated-bench-handoff.md`, `isolated-postgres16-correction.md`. Les chemins et versions locaux ne sont pas présentés comme ceux du Debian opérationnel.

## CI finale au SHA examiné

[AIOps quality gates — run42702493327](https://github.com/alimtalbi-ata/aiops/actions/runs/42702493327), événement push, commit exact e7c76514b8e98cb35a9594226e7106fde98a42aa : **SUCCESS**. Six jobs PASS : quality-build-package, database-migrations, mariadb-dr-rehearsal, migration-runner-upgrade, runtime-e2e et release-kit. Le job PostgreSQL a réussi l'installation, les migrations, la restauration DR, les contrôles d'intégrité et les réapplications de migrations. Instantané expurgé des liens/conclusions : `isolated-final-ci.json`.

Le job nommé runtime-e2e est une qualification CI avec fournisseur déterministe synthétique ; il ne vaut pas preuve E2E FS1250/GLPI réelle.

## Défauts rencontrés et traitement

1. Temporal dev : deux arrêts de scanner conservés. Épinglage1.4.1 seul insuffisant ; correction des appels locaux 0.0.0.0 pour éviter le proxy sur les seules communications internes, sans suppression de scanner ou garde. Nouveau Run et replay PASS ; disponibilité longue durée non démontrée.
2. Run42699163023 au SHA e0fc66c3 : DR PostgreSQL échoué. Le journal relu par le connecteur utilisateur indique `SET transaction_timeout = 0`, non reconnu par PostgreSQL16.15. Codex n'a pas prétendu accéder à ce journal API. Correction : aligner clients et serveur sur16, journaliser leurs versions/chemins, refuser les majors incompatibles ; aucun filtrage SQL.
3. Run42702179382 au SHA8011ddd6 : installation APT échouée avec100. Absence du paquet client16 reproduite sur Ubuntu26.04 ; installation et trois versions réussies sur Ubuntu24.04. Second commit : fixer le seul job PostgreSQL sur Ubuntu24.04. CI suivante entièrement réussie.
4. Première reproduction DR précédente incomplète faute de Python3 dans l'image PostgreSQL ; elle n'était pas une reproduction équivalente. La vérification complète ultérieure utilise une image jetable avec Python3 et passe ; preuves conservées.

## Blocages et limites conservés

- PR DRAFT : descriptif conservé dans `isolated-draft-pr.md` ; API GitHub CONNECT403, aucune PR ni commentaire d'issue créé par Codex, aucune nouvelle tentative API. Le descriptif initial précède les deux corrections PostgreSQL ; lire ce rapport et `isolated-postgres16-correction.md` avec lui pour le périmètre final. Publication disponible par Git HTTPS.
- Revues Core/Worker non obtenues. Les corrections récentes non portées restent à examiner séparément ; pas d'import global d'arbres, ni de remplacement Debian retenu sur une provenance de checkout inconnue.
- GLPI authentifié, corrélation indépendante, navigateur, modèle réel et approbation OIDC réelle non qualifiés. Aucun ticket réel créé ; aucune écriture PostgreSQL/GLPI de production.
- **DEBIAN HOLD ; FS1250 HOLD ; E2E RÉEL HOLD.** Les succès locaux et CI ne lèvent aucun de ces états.
- Aucun merge, déploiement, changement cron/Compose de production ou nettoyage des checkouts d'autres agents. Les ressources jetables propres aux vérifications ne constituent aucun déploiement opérationnel.

## Expurgation et fin de mission

Ce rapport et l'instantané CI contiennent uniquement SHA, chemins du dépôt/de qualification, résultats, identifiants synthétiques et liens GitHub publics ; aucun token, mot de passe, configuration privée, identité OIDC réelle ni donnée GLPI. Les configurations privées de banc ne sont pas ajoutées à Git. Les preuves précédentes avaient été contrôlées contre les secrets propres aux bancs ; les transformations de logs sont documentées.

La reprise nocturne appartient au CLI Debian. Ce handoff ne lance aucune action supplémentaire et ne transmet aucune autorisation de déploiement.
