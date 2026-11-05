# Consignes Claude Code optionnelles — AIOps2 V28

Document de référence non auto-chargé ; ne pas copier à la racine sans revue.

## Orchestration
- Analyste métier : exigences, vocabulaire, cas d'acceptation.
- Architecte : contrats, dépendances, ADR, frontières de confiance.
- Développeur : tranche verticale isolée et réversible.
- Testeur : tests reproductibles, négatifs, anti-rejeu.
- Sécurité : identité/tenant, OIDC, STOP_AUTO, secrets, aucun effet LIVE.
- Reviewer : preuves exact-SHA et cohérence des états.

## Gates
SPEC_REVIEWED → DESIGN_REVIEWED → SOURCE_CREATED → CI_EXACT_SHA → APPROVED → HOST_EXECUTED → EVIDENCE_PUBLISHED.
Aucun gate ne se déduit du précédent. Schémas, permissions, politique et migrations requièrent approbation explicite.

## Pilote
Filesystem synthétique #423, reçu #428, branche stable protégée, canal Debian existant uniquement. Pas de nouveau cron ni de dispatcher. Pas de manipulation des cinq fichiers non committés du checkout Debian.
