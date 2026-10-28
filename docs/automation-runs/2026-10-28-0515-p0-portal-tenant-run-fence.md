# Exécution P0 NOC — 2026-10-28 05:15 Europe/Paris

- **Démarrage :** mercredi 2026-10-28 05:15 CET (+01:00).
- **Dépôt / base :** `alimtalbi-ata/aiops`, `main` HEAD relu avant création et écriture : `1ed749129e32ea9a8854c437c7de9a6a8b43e35b`.
- **Revue préalable :** main, PR ouvertes #36, #37, #39, #41, #43 et PR concurrentes #58, #71, #75, #78, #83 ; `docs/PROJECT-CONTINUITY.md`, `docs/COMPONENT-CATALOG-AND-REUSE.md`, `docs/ARCHITECTURE-AND-BOUNDARIES.md`, `docs/DECISION-LOG.md`, `docs/OPERATIONAL-FLOWS.md`, `docs/TEST-STRATEGY.md`, `.github/workflows/quality.yml`.
- **Branche dédiée :** `fix/portal-run-inventory-tenant-fence-20261028-0515`.
- **PR :** [#88](https://github.com/alimtalbi-ata/aiops/pull/88), **draft**, non fusionnée.
- **Commits de code/tests/docs :** `55687e6cf568fb5ad495cd544622c9cb261be307`, `a98a0edbee6f396693982d274a5dae6b21f776d6`, `c2849de08d676ef0d6fa4ff0584d1f9d4a890080`. Ce journal est ajouté par commit séparé ; son SHA est disponible dans l'historique de la PR.
- **Fichiers modifiés :** `app/portal/portal_read_models.py`, `tests/test_portal_read_models.py`, `docs/architecture/PORTAL-RUN-INVENTORY-TENANT-FENCE-20261028.md`, présent journal.
- **Micro-lot :** fail-closed de l'inventaire Run dès qu'une portée tenant/org/workspace/account est rencontrée, y compris imbriquée, nulle ou non inspectable. Les deux surfaces existantes du portail affichent UNKNOWN au lieu de divulguer les Runs. `tenant_acl_qualified=false` explicite.
- **Portage PR #36 :** modules NOC/RAG déjà repris sur main ; pas de copie supplémentaire utile dans ce lot. Aucun merge massif.
- **CI effectivement exécutée :** workflow **existant** `.github/workflows/quality.yml`, [run pull_request 40631445560](https://github.com/alimtalbi-ata/aiops/actions/runs/40631445560) sur HEAD `c2849de08d676ef0d6fa4ff0584d1f9d4a890080` : **completed/success** ; job `policy-and-static` et étapes Python compile, tests Portal read model (nouveaux cas négatifs et non-régression), sécurité NOC/corrélation/RAG, préflight secrets, audit statique et `docker compose config` : **success**. [Run push 40631433443](https://github.com/alimtalbi-ata/aiops/actions/runs/40631433443) : **completed/success**. La CI du commit de journal est à revérifier après écriture.
- **Tests non exécutés / NOT_TESTED :** aucun Core multitenant réel, Checkmk/Thruk, Grafana observé, NIM/Ollama, E2E navigateur ou serveur Debian ; les tests de cette livraison sont unitaires/contrats et statiques, sans preuve LIVE.
- **Risques :** ce filtre ne remplace pas une ACL tenant/actor en Core ; un fournisseur omettant tous les champs de portée peut rester `READABLE_UNVERIFIED`. La limite de profondeur est conservatrice et peut masquer un inventaire pourtant légitime : choix de sécurité intentionnel. Aucune attestation d'isolation multitenant.
- **Blocages :** identité tenant authentifiée et politique Core non disponibles/qualifiées ; services réels non vérifiés.
- **Prochain micro-lot :** ajouter un contrat de principal tenant authentifié côté Core, puis tests d'isolation inter-tenants contre Core éphémère, avant d'exposer des données tenant ; conserver les étapes Checkmk/Thruk → Incident/Run → Grafana → RAG en lecture seule.
- **Actions interdites :** aucun accès à `10.79.94.202`, aucune commande LIVE, aucun déploiement, aucune fusion.
