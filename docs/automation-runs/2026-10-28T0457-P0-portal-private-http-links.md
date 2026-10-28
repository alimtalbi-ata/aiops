# P0 — Durcissement des liens HTTP LAN du portail

- **Début** : 2026-10-28 04:57:03 Europe/Paris (UTC+01:00).
- **Dépôt** : `alimtalbi-ata/aiops`.
- **SHA de départ de main** : `1ed749129e32ea9a8854c437c7de9a6a8b43e35b` (vérifié avant branche et toujours inchangé lors du contrôle de 04:59).
- **Branche dédiée** : `fix/p0-portal-private-link-ranges-20261028`.
- **PR draft** : [#87](https://github.com/alimtalbi-ata/aiops/pull/87), non fusionnée.
- **Commit code/tests/docs** : `b2ec6b95cd663f8b2c5cbab66951d2ca49f66059`.
- **Portage PR #36** : registre `app/portal/platform_registry.py` déjà porté sur main (blob d'origine `969b5f7fdc4f654cca5f6d3b6ed6e2a004f5fd8d`), réutilisé sans merge massif. PR #37/#39/#41/#43 consultées ; roadmap PR #39 lue. Aucun fichier de ces PR n'a été écrasé.

## Fichiers

- `app/portal/portal_integrations.py` : le navigateur ne reçoit un lien HTTP opt-in que pour IPv4 RFC1918 ou IPv6 ULA. Les plages spéciales non LAN acceptées par `ipaddress.is_private` sont rejetées.
- `tests/test_portal_integrations.py` : tests négatifs de plages réservées/documentation/benchmarking, tests positifs RFC1918/ULA, vérification de non-divulgation dans la navigation.
- `docs/portal/INTEGRATION-NAVIGATION-P0.md` : portée, compatibilité et limites du changement.
- `docs/automation-runs/2026-10-28T0457-P0-portal-private-http-links.md` : présent journal.

## Tests réellement exécutés

- **Local, Python stdlib (contrôle ciblé de la logique CIDR)** : 5 adresses autorisées et 12 rejetées, **PASS**. Ce contrôle ne remplace pas le test du module complet.
- **GitHub Actions existant** `.github/workflows/quality.yml`, [run 40629675825](https://github.com/alimtalbi-ata/aiops/actions/runs/40629675825), commit `b2ec6b9` : **completed / success**. Job `policy-and-static` : compilation, policy, tests de navigation et read models, NOC signé/corrélation/RAG, impact ACME, preflight secrets, audit statique et `docker compose config` : étapes toutes **success** selon les jobs GitHub.
- **Intégration n8n/Thruk/Grafana/GLPI/Checkmk en conteneurs réels** : **NOT_TESTED**. Le workflow qualité ne démarre pas ces services.
- **Ollama 4B / NVIDIA NGX** : **NOT_TESTED**, hors périmètre de ce changement ; aucune équivalence 192B revendiquée.
- **Navigateur authentifié / capture réelle / Debian 10.79.94.202 / portail 17777** : **NOT_TESTED**, aucun accès ni déploiement.

## Risques, blocages, suite

- Changement intentionnel : les URLs HTTP de plages spéciales (y compris les plages de documentation) auparavant acceptées seront désormais `REJECTED_CONFIGURATION`. Les URLs HTTPS ne changent pas. Le validateur ne fait aucune résolution DNS et ne prouve ni identité ni disponibilité du service.
- Blocage P0 principal inchangé : protections RBAC dispersées entre PR #51/#57/#70/#74 ; intégration de services et captures authentifiées non qualifiées.
- **Prochain micro-lot** : convergence contrôlée des protections du bootstrap, des commandes DEMO/Copilot et des vues opérateur, avec tests de refus avant appels upstream ; ne pas fusionner les PR divergentes en bloc.
- **Sécurité** : aucune action LIVE, aucune commande SSH, aucun merge ni déploiement. Les états de service restent UNKNOWN.
- **Note CI** : l'ajout de ce journal crée un commit documentaire ultérieur ; vérifier séparément son exécution GitHub Actions et consigner le lien dans la PR si disponible.
