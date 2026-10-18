# AIOps V7.8 — développement cloud

V7.8 est la livraison de référence. Le Foundation Kit est une version initiale ;
il ne doit pas être superposé aux services actuels.

Les dépendances Python sont déclarées dans `app/requirements.txt`.
Les contrôles suivants n'exigent pas de secret ni de connexion de production :

```sh
bash tests/v78-static-gate.sh
bash tests/static-audit.sh
bash tests/sql-audit.sh
bash tests/runtime-contract.sh
```

Le cloud a vérifié les services Policy et Core, une base PostgreSQL 16 isolée,
les 14 migrations sur une base neuve, la création persistante d'un run DEMO,
l'idempotence et le tableau de bord. Les paramètres et jetons de développement
restent hors du dépôt. Aucun système externe n'a été modifié.

La pile Compose complète (Temporal, worker, intégrations, GLPI, n8n et observabilité)
et les scénarios de qualification de bout en bout restent à exécuter séparément.
La réussite des contrôles locaux ne constitue pas une qualification de production.
Les scripts de retrait d'anciennes installations ne font pas partie de cette validation.
