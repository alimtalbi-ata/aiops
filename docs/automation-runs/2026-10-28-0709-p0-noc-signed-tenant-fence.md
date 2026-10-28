# P0 NOC — signed tenant-scope fence (2026-10-28 07:09 Europe/Paris)

- **Départ main:** `88cb4ed01706ac09bb8e01fdceead422cab2590d` (GitHub ref vérifié avant modification).
- **Branche:** `fix/noc-signed-tenant-scope-fence-20261028-0709` (dédiée; aucune modification des branches des autres créneaux).
- **Références lues:** main, PR ouvertes #36/#37/#39/#41/#43, PR #71 et #75, continuité/roadmap, `quality.yml`, adaptateur NOC et tests; portage ciblé de l'interface NOC déjà intégrée depuis #36, pas de merge massif.
- **Fichiers:** `app/portal/noc_runtime.py`, `tests/test_noc_tenant_scope_fence.py`, `docs/PROJECT-CONTINUITY.md`, `docs/architecture/NOC-SIGNED-READMODEL-BRIDGE-20261027.md`, ce journal.
- **Code:** refus fail-closed des claims tenant/org/workspace/account/customer (même imbriqués, null ou Unicode), borne de parcours; HMAC seul ne qualifie aucune ACL. Le contrat signé non scopé reste inchangé.
- **Tests préparés:** cas positifs, variantes de scope, profondeur, borne, redaction HTTP 503/no-store; unitaires/contractuels avec upstream HTTP remplacé uniquement dans le test, **pas une intégration Checkmk/Thruk**.
- **Tests exécutés/résultats:** PENDING — aucun PASS revendiqué avant GitHub Actions; `quality.yml` existant exécute la suite NOC, étape dédiée à ajouter.
- **Commit/PR:** PENDING — remplir après confirmations GitHub.
- **Risques:** refus conservateur de payloads avec métadonnées de scope même non utilisées; pas de RBAC tenant ni de liaison observée Checkmk/Thruk; pas d'inférence LLM ni Grafana qualifié.
- **Blocages:** intégration Core tenant, vrais services éphémères et contrat de preuve non disponibles dans ce micro-lot: NOT_TESTED/BLOCKED.
- **Prochain micro-lot:** authentifier l'identité tenant dans Core puis tester A/B avec Core réel éphémère; raccorder Checkmk/Thruk réel seulement après qualification de l'ACL.
- **LIVE:** aucune commande, fusion, migration, déploiement ou accès Debian/portail.

## Vérification GitHub — 2026-10-28 07:11 Europe/Paris

- **PR draft créée :** [#99](https://github.com/alimtalbi-ata/aiops/pull/99).
- **Commits confirmés :** `a28b1579f91e4b1014a6a00e00df713953a7b831` (code, tests, docs et journal initial) ; `ea3a46c231a30909c8d759a2f151f72a5ac46864` (ajout de l'étape dans `.github/workflows/quality.yml`). Ce workflow est également un fichier modifié.
- **CI push vérifiée :** [run 40642298144](https://github.com/alimtalbi-ata/aiops/actions/runs/40642298144), `completed/success`, HEAD `ea3a46c`. Logs consultés : **5 tests tenant-scope exécutés, 5 OK** (unitaire/contractuel), compilation, tests NOC existants, audit statique et validation Compose réussis.
- **CI PR vérifiée :** [run 40642312111](https://github.com/alimtalbi-ata/aiops/actions/runs/40642312111), `completed/success`, même HEAD.
- **Limite de qualification :** transport amont remplacé dans le test de route, aucun service Checkmk/Thruk, Core tenant, Grafana ou Ollama éphémère exécuté par ce micro-lot : **NOT_TESTED**. Aucun secret NGX, aucun appel à un équipement ou serveur LIVE.
- **Journal final :** cette mise à jour documentaire déclenche une nouvelle vérification CI; son statut doit être lu sur le nouveau HEAD avant toute fusion.
