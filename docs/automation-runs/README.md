# Journal des executions planifiees

Chaque schedule P0/P1 doit consigner dans GitHub ses actions, decisions, projets de developpement, problemes rencontres, tests et resultats reels.

## Modele obligatoire

- Date UTC, schedule, branche, SHA initial et PR.
- Actions effectuees, fichiers modifies et liens des commits.
- Decisions, raisons et alternatives.
- Problemes, echecs, blocages et risques.
- Tests executes, resultats, preuves et tests non executes.
- Prochaines etapes, dependances, criteres d'acceptation.
- Etat de qualification et conditions de rollback.

Utiliser un fichier date par execution sous docs/automation-runs/. Mettre a jour les cinq documents canoniques si necessaire. Toujours travailler en branche et PR brouillon; jamais de merge automatique ou deploiement de production. Si GitHub refuse une ecriture, signaler le blocage explicitement.
