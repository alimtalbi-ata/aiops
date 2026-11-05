# Évaluations agentiques AIOps2

Cas à reprendre du paquet source : besoin flou, validation workflow, règle de calcul, droits/périmètre.

Ajouter les contrôles AIOps2 suivants avant toute activation :
- refus d'un acteur/tenant non autorisé et de tout contournement OIDC/STOP_AUTO ;
- aucune action LIVE sur proposition synthétique ;
- refus de réutilisation d'un run-id et vérification rollback ;
- séparation des preuves CI et des reçus hôte ;
- protection du checkout Debian non commité.

Les évaluations génériques de l'archive utilisent des regex et ne constituent pas une attestation de sécurité ni une preuve E2E.
