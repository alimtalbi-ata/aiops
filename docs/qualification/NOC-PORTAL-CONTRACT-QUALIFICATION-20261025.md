# Qualification du contrat NOC / portail unique — 2026-10-25

## Résultat CI observé

Commit qualifié : `1e3d80488f3608b9b3aab19b877be8192c501836`

- **Single-portal cumulative candidate kit (offline)** : succès, run [40182917035](https://github.com/alimtalbi-ata/aiops/actions/runs/40182917035).
- **STAR Chromium read-only fixture qualification** : succès, run [40182916953](https://github.com/alimtalbi-ata/aiops/actions/runs/40182916953).
- **AIOps quality gates** : succès, run [40182916954](https://github.com/alimtalbi-ata/aiops/actions/runs/40182916954).

Ces résultats attestent les workflows GitHub ci-dessus sur ce commit. Ils ne constituent pas une preuve d'exécution sur le serveur Debian cible.

## Contrôles ajoutés

- Horodatages UTC stricts : une valeur doit se terminer par `Z`, être analysable et correspondre à un instant UTC valide.
- Les booléens ne sont pas acceptés comme politique numérique de fraîcheur.
- Une observation future, périmée ou non authentifiée ne rend pas un composant sain ; son état reste `UNKNOWN`.
- Les charges d'observation malformées sont rejetées avec une erreur de validation explicite.
- Les 20 composants sont listés, mais leur présence dans le registre ne prouve pas le montage de leur route.
- L'autorisation de remédiation LIVE reste explicitement à `false`.

## Limites bloquantes

Le routeur de contrat `demo/noc_portal_integration.py` n'est pas encore monté dans le processus qui sert `http://10.79.94.202:17777/`. Aucun résultat de cette qualification ne prouve l'état réel de Checkmk, Thruk, Grafana, Prometheus, Alertmanager, GLPI, n8n, Temporal ou DGX sur le serveur cible.

Avant toute mise en service :
1. auditer en lecture seule le processus et la configuration du portail existant ;
2. identifier une source de read model issue du pipeline réellement exécuté et son mécanisme d'authentification ;
3. monter les routes uniquement dans une copie d'intégration avec les middlewares d'authentification existants ;
4. exécuter l'E2E de bout en bout et conserver les preuves, les logs expurgés et le plan de rollback ;
5. demander l'approbation explicite avant toute modification du portail de production.

**Aucun déploiement, redémarrage, changement de port ou action de remédiation LIVE n'a été effectué par cette qualification.**
