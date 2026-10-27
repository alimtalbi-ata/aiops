# CI — reprise bornée des pertes de transport BuildKit (26 octobre 2026)

## Incident observé

Le workflow AIOps quality gates, run 40395962359, a échoué au premier essai sur l'étape Build every application image. Les tests Python précédents et la validation du modèle Compose avaient réussi ; BuildKit a ensuite renvoyé une erreur RPC Unavailable / error reading from server: EOF sur la cible aiops2-copilot.

La relance des seuls jobs en échec a ensuite terminé le job quality-build-package avec succès sur le même HEAD b9e6b5d66689c7134f4a49098e764eac15bdbb16. Le job release-kit était encore en cours au dernier contrôle de cette tentative ; ce résultat ne vaut donc pas qualification complète du workflow.

## Politique ajoutée

Le helper tools/ci_docker_build.py enveloppe les commandes Compose qui construisent des images dans le workflow quality.yml :

- deux tentatives au maximum, avec un délai fixe de deux secondes ;
- seconde tentative uniquement pour trois signatures BuildKit/daemon révisées, dont le RPC Unavailable avec EOF observé dans le workflow ;
- aucune nouvelle tentative pour une erreur de syntaxe Dockerfile, un échec de test ou toute autre erreur non reconnue ;
- un second échec reste un échec CI : aucun continue-on-error et aucun succès forcé ;
- les arguments Compose sont identiques aux deux tentatives, permettant de réutiliser le cache normal quand il est disponible.

La politique s'applique au build de toutes les images applicatives, au démarrage du graphe E2E avec --build et au runner d'évaluation optionnel. Le démarrage retenté est limité à la stack CI isolée ; aucun environnement opérationnel n'est visé.

## Régressions

tests/test_ci_docker_build.py vérifie le retry après la signature EOF, l'absence de retry sur les erreurs déterministes, l'échec après deux tentatives, les arguments Compose, l'appel sans argument et l'absence de divulgation du chemin local lorsqu'un exécutable manque.

Les tests utilisent un runner substitué : ils n'appellent pas Docker, ne téléchargent pas d'images et ne créent aucun conteneur.

## Qualification et rollback

La qualification du nouveau workflow doit confirmer les tests de contrat, les builds Compose, l'E2E isolé, les migrations/DR et la génération du kit. Cette modification n'autorise aucune promotion à elle seule.

Rollback source-only : rétablir les commandes directes docker compose dans .github/workflows/quality.yml, puis retirer tools/ci_docker_build.py, tests/test_ci_docker_build.py et ce document. Aucun rollback applicatif ou runtime n'est nécessaire.
