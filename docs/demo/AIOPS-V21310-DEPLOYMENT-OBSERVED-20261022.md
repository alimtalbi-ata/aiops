# V2.13.10 — Qualification de déploiement (opérateur, 2026-10-22)

## État observé sur SRV-DEB-05
- Conteneur `aiops2-rebuild-portal` : `Up (healthy)`.
- Service Compose `aiops2-portal`, image `aiops2-portal:v21310`.
- Publication unique : `10.79.94.202:17777->777/tcp`.
- Image cible inspectée : `sha256:3405a8b2317816e3681f26848b31f27386126e7c2c81a994cd5e5a187dac5fe4`.
- `/health` : 200; `/` : 200; `/demo/` : 200; `/demo/star` : 200.
- `/demo/view/AIOPS-REAL-STACK-REPLAY.html` : 403 (historique bloqué).
- `docker compose ... ps -q aiops2-portal` retourne l'ID conteneur : confirmé.
- L'import et le routage ASGI de la candidate avaient préalablement passé leurs contrôles hors réseau.
- Les contrôles navigateur STAR et le contrôle effectif de toutes les API d'écriture ne sont pas couverts par ces résultats.

## Problème du script initial
Le script de déploiement a retourné « no such object: aiops2-rebuild-portal » lors d'un `docker inspect` final, alors que les contrôles HTTP étaient tous à 200. Un diagnostic ultérieur retrouve le conteneur et son service `healthy`. Il ne faut pas expliquer l'échec initial par une cause précise non prouvée.

## Suite technique
- Mettre à jour le script de déploiement en récupérant le conteneur avec `docker compose ps -q aiops2-portal` au lieu d'un nom fixe.
- Vérifier l'ID image active avec `docker inspect "$(docker compose ... ps -q aiops2-portal)" --format '{{.Image}}'`.
- Tester le playback, les commandes pause/suivant/recommencer et les erreurs JS dans un navigateur.
- Conserver `AIOPS_DEMO_HISTORICAL_APPROVED=false` et `AIOPS_DEMO_LAUNCH_ENABLED=false` tant que la revue des accès n'est pas achevée.
- Ne pas confondre simulation STAR et exécution DGX / remédiation LIVE.
- Préserver les fichiers Compose locaux; ne jamais publier de second portail.
