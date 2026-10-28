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
