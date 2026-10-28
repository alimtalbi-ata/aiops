# 2026-10-28 11:15 Europe/Paris — P0 Worker / Policy simulation fence

## Contexte, source et intégrité
- Départ `main` revérifié avant création et toute écriture : `5d757869a46f427b1885a19ce019ca29a18063fd`. Un premier relevé de `main` à `723ca6458c722a1aa0e57ddb5eee3374d20cc830` avait changé avant la modification ; aucune écriture sur cet ancien HEAD.
- PR relues : #36 (source de contrat), #37, #39, #41, #43, #49, #72 et pile HITL #106 ; PR concurrente #124 désormais intégrée à `main`. Continuité, README, architecture, décisions, catalogue, protocole de qualification et workflow `quality.yml` consultés.
- Branche dédiée : `fix/p0-worker-mode-policy-fence-20261028-1115`, issue du SHA exact ci-dessus ; pas de modification directe de main, pas de merge massif ni d'écrasement de branches tierces.
- Portage ciblé depuis la PR #72 (qui réutilise #36) : `app/shared/simulation_policy_contract.py` et `tests/test_simulation_policy_contract.py`. Le Worker courant est adapté à ce contrat.

## Fichiers et commits
- `app/shared/simulation_policy_contract.py` : `50b78ec3dc7493b90ff80fd937f2b236f0850fa5`.
- `app/worker/main.py` : `aa7fcd8722beb6515c6082ade581b8cf17e58e11`.
- `tests/test_simulation_policy_contract.py` : `d1a73f605f08574967907c6057d63330c04d1fbb`.
- `.github/workflows/quality.yml` : `aa9cf430e354450f09a52fcefa3b10c34889a260`.
- `docs/PROJECT-CONTINUITY.md` : `a6249e0f987940972feb89dd071a7c9db6baab41`.
- Ce journal : commit initial `fdcf54d6a5f2c1234345d4a098d5e309d498117c`, suivi du présent ajout de références.
- PR : [#126](https://github.com/alimtalbi-ata/aiops/pull/126), draft, non fusionnée ; base `5d757869a46f427b1885a19ce019ca29a18063fd`.
- CI PR initiale : [quality #40670937204](https://github.com/alimtalbi-ata/aiops/actions/runs/40670937204), **queued/in_progress lors de la consignation** ; ne pas déclarer PASS sans résultat. Après cet amendement documentaire, vérifier la CI sur le nouveau HEAD.
- Aucune modification du schéma, aucun déploiement, aucun secret.

## Contrat de sécurité
- Modes DEMO/REPLAY/STORY → commande Policy `OBSERVE` ; LIVE → `EXECUTE`, toujours soumis au blocage LIVE existant.
- Mode inconnu rejeté avant l'événement de stage, Twin/Evidence, et avant la connexion Temporal côté HTTP.
- Tests négatifs de mode et vérification AST de l'ordre des gardes ; ne prouvent pas un vrai E2E.

## Qualification, limites et risques
- Au moment de la création de ce journal : tests et checks de ce nouveau HEAD **NOT_TESTED / en attente**. Le workflow GitHub Actions existant doit être vérifié sur son SHA final, avec URL et conclusion ; ne pas assimiler une PR ouverte à un PASS.
- Tests Core/PostgreSQL et Grafana : jobs existants de `quality.yml`, à vérifier séparément ; ils ne constituent pas une intégration Worker/Temporal.
- **NOT_TESTED** : Temporal réel, Policy HTTP couplée au Worker, Core/Twin/Evidence enchaînés, HITL authentifié, Ollama 4B, navigateur, captures/vidéo, Debian et LIVE.
- Risque : le Worker synthétique conserve son comportement historique de stages HITL/REMEDIATE/VERIFY avec preuves synthétiques ; ni approbation humaine ni postcheck/rollback exécuté ne peuvent en être déduits. Le contrat de mode est un garde-fou, pas une preuve de remédiation.

## Prochain micro-lot
Réconcilier sélectivement le HITL sandbox #49→#106 sur `main`, raccorder identité opérateur et IDs Core au workflow Temporal sandbox, puis afficher des étapes HITL/REMEDIATE/VERIFY explicitement SIMULATED/NOT_EXECUTED, avec vrais conteneurs éphémères pour Core/Temporal/Policy/Twin/Evidence et tests de refus/rejeu. Aucune commande libre LLM ni effet LIVE.

## Qualification GitHub Actions vérifiée après exécution

- Commit code+journal initial `fdcf54d6a5f2c1234345d4a098d5e309d498117c` : [quality #40670937204](https://github.com/alimtalbi-ata/aiops/actions/runs/40670937204) — trois jobs terminés **success** : `policy-and-static` (dont le nouveau test Worker, compilation, Policy, portail, audit et Compose), `core-postgres-noc-real-integration` (Core HTTP + PostgreSQL éphémères) et `grafana-real-integration` (Grafana HTTP éphémère). Vérification des étapes de `policy-and-static` : chaque étape terminée `success`.
- Commit de documentation et référence PR `0461631c72032054b3fa3dbb813d4eec89495946` : [quality #40670987107](https://github.com/alimtalbi-ata/aiops/actions/runs/40670987107) — mêmes trois jobs **completed/success** vérifiés.
- La présente mise à jour de journal crée un nouveau commit et déclenche potentiellement un autre run : son statut devra être vérifié séparément avant toute fusion. Ces succès ne prouvent pas le couplage Worker/Temporal/HITL ; Core/PostgreSQL et Grafana ont été exercés dans des jobs indépendants.
