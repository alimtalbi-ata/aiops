# 2026-10-28 07:38 CET — P1 ACME / ITSM : verrou Run autorisé

- **Dépôt :** `alimtalbi-ata/aiops`. `main` inspecté à `88cb4ed01706ac09bb8e01fdceead422cab2590d` avant modification.
- **Base de développement :** PR #96, HEAD vérifié `e8205f3a92f69a69ae5a90338da00a2ef338696d`, empilée sur PR #90. PR #36, #37, #39, #41, #43 consultées ; continuité/roadmap et `.github/workflows/quality.yml` lus. Aucun merge massif de PR #36.
- **Branche isolée :** `feat/p1-acme-itsm-run-scope-20261028-0738` ; [PR #101](https://github.com/alimtalbi-ata/aiops/pull/101) (draft, base PR #96).
- **Commit code/tests/docs :** `20db3922784fc32fb4b6136c168f58c17fcf018d`.
- **Fichiers modifiés :** `app/shared/acme_itsm_binding.py`, `tests/test_acme_itsm_binding.py`, `docs/demo/ACME-ITSM-SIGNED-BINDING-20261028.md`, `docs/PROJECT-CONTINUITY.md`, `docs/DECISION-LOG.md` ; présent journal ajouté.
- **Changement :** `authorized_run_id` obligatoire, vérifié contre le Run canonique et le reçu HMAC ; la seule autorisation d'entité GLPI ne suffit pas à lire une autre liaison Run. Retour `UNKNOWN` sans identifiants si portée absente, invalide ou discordante. Aucune API réseau ou écriture ajoutée.
- **Tests ajoutés :** portée Run absente/malformée et rejeu inter-Run dans la même entité GLPI avec signature synthétique valide ; contrôle de non-régression positif `CONTRACT_MATCHED_UNATTESTED` et refus LIVE existants.
- **Tests exécutés / résultats :** en attente de GitHub Actions sur HEAD final de PR #101 ; **NOT_TESTED** à l'écriture initiale de ce journal. Le workflow existant `quality.yml` contient l'étape `test_acme_itsm_binding.py` et les contrôles Policy/NOC, compilation, audit, Compose. Aucun PASS anticipé.
- **Risques / blocages :** la portée Run doit provenir d'un RBAC serveur authentifié, pas du navigateur ; aucun vrai Core, GLPI, Temporal ni émission HMAC Core qualifiés. Pas de ticket GLPI réel, pas de preuve LIVE, pas de capture/vidéo authentifiée. CI avec services éphémères **NOT_TESTED** ; NGX réel non contacté et aucun LLM CI simulé dans ce lot.
- **Sécurité / rollback :** aucune connexion Debian `10.79.94.202`, au portail `:17777`, aucun déploiement, migration, secret de production, fusion ou commande LIVE. Revert ciblé du commit de contrat possible.
- **Prochain micro-lot :** obtenir `authorized_run_id` et `authorized_entity_id` d'une identité RBAC Core/portail vérifiée, puis qualifier GLPI via un vrai service conteneurisé CI, avec refus explicite si indisponible.

## 07:40 CET — CI du commit de code vérifiée

- [GitHub Actions 40645261657](https://github.com/alimtalbi-ata/aiops/actions/runs/40645261657) sur `20db3922784fc32fb4b6136c168f58c17fcf018d` : **completed / success** (consultation des jobs et étapes).
- Job `policy-and-static` : **success**. Étapes vérifiées : compilation Python, tests Policy, portail, NOC, ACME impact, **ACME signed ITSM binding**, préflight secrets, audit statique et `docker compose config` : **success**.
- **Périmètre réel :** tests unitaires/contrat hors ligne, audit statique et validation syntaxique Compose. **NOT_TESTED :** GLPI/Core/Temporal conteneurisés, RBAC serveur effectif, LLM CI Ollama, captures réelles, vidéo, LIVE. Aucun service GLPI simulé présenté comme intégration.
- Commits de journal : `eadeffcc5976ac96739526ed35c36816f21c21ce` puis `a31e17c182a3b554f3dc95834db0c5ce19acc343` (mise à jour de la preuve CI). Le check du HEAD documentaire final doit être vérifié séparément.
