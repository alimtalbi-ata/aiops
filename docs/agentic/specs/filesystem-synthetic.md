# Spécification — cycle filesystem synthétique

Statut : proposé, non validé pour exécution hôte.

**But** : démontrer saturation logique, détection, proposition, action synthétique, vérification, rollback et preuve publiée.

- Capacité logique 12 MiB ; usage 11 MiB ; seuil 75 %.
- Action cleanup-logs : 6/12 MiB ; alternative expand-fs : 11/16 MiB.
- Rollback : 11/12 MiB, incident OPEN_SIMULATED, aucun effet LIVE.
- Un run-id canonique, une action à la fois, approbation SYNTHETIC_APPROVED, flock, état JSON, SHA256.
- Réutiliser exclusivement le poller/publisher Debian existant après revue de son contrat.
- Refuser toute ambiguïté, symlink dangereux, utilisateur non autorisé ou état incohérent.

**Acceptation** : reçu hôte SRV-DEB-05 frais, SHA source épinglé, attestation état final/rollback, publication vérifiée. Tests CI seuls insuffisants.
