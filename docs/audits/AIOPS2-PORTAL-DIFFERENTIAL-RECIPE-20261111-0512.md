# AIOPS2 — recette différentielle navigation et ACL (2026-11-11 05:12 Europe/Paris)

## Portée et niveaux de preuve
Source inspectée : `app/portal/main.py` sur main, blob `16d156c912ccc7592383f7d67a6a6a36fef50629`. Cette lecture de source ne prouve ni CI, ni déploiement, ni HTTP, ni E2E. Portail actif SRV-DEB-05 : image précédemment déclarée `a1f3adcf1e11`, port 7777 (2026-11-10) ; candidat 10.79.94.202:17778 ; rollback fs1073/fs1051/fs621 ; sources v28/V145 : provenance binaire, correspondance des SHA et réponses HTTP **UNKNOWN** à ce cycle. Aucun accès Debian direct attesté : **DEBIAN UNKNOWN**. E2E **NON VERIFIÉ**.

## Matrice avant/après et décision
| Fonction / route | Avant (v28/V145/rollback) | Source main observée | Actif 7777 / candidat 17778 | Cause possible / priorité | Restauration conditionnelle |
|---|---|---|---|---|---|
| Dashboard, Core/Twin/Runs : GET /api/portal/bootstrap | UNKNOWN | Après authentification viewer, 503 UNKNOWN / TENANT_ACL_NOT_QUALIFIED ; pas de lecture Core/Twin | UNKNOWN / UNKNOWN | Contrat ACL tenant non qualifié ; P0 sécurité | Ne pas restaurer la lecture sans autorisation tenant/acteur dérivée serveur |
| Navigation, NOC/GLPI : GET /api/portal/components | UNKNOWN | Après viewer, 503 UNKNOWN / TENANT_ACL_NOT_QUALIFIED ; registre non lu | UNKNOWN / UNKNOWN | Liens potentiellement absents par refus voulu ; P0 sécurité | Comparer le shell statique et les contrats autorisés, sans révéler URL opérateur |
| Copilot : POST /api/copilot | UNKNOWN | Après viewer, 503 UNKNOWN / TENANT_ACL_NOT_QUALIFIED ; pas de transfert amont | UNKNOWN / UNKNOWN | Contrat tenant/run absent ; P0 sécurité | Requalification ACL préalable |
| DEMO / Runs : POST /api/demo | UNKNOWN | Après authentification opérateur, 503 UNKNOWN ; mutation refusée | UNKNOWN / UNKNOWN | HITL/ACL insuffisants ; P0 sécurité | Aucun rétablissement de mutation par le portail |
| Evidence, NOC, GLPI, visualisation, UX | UNKNOWN | Routeurs NOC et GLPI inclus ; comportement des écrans non attesté | UNKNOWN / UNKNOWN | P1 audit fonctionnel | Comparaison DOM, accessibilité, états vides, erreurs et provenance |

## Recette négative reproductible (hors production)
1. Sur checkout isolé au SHA candidat, utiliser TestClient et doubles de services amont qui échouent si appelés. Ne jamais employer de jeton réel.
2. GET /api/portal/bootstrap, GET /api/portal/components, POST /api/copilot avec un viewer fictif valide mais sans ACL tenant qualifiée : attendre HTTP 503, `state=UNKNOWN`, `reason=TENANT_ACL_NOT_QUALIFIED`, zéro appel Core/Twin/Copilot/registre.
3. POST /api/demo avec opérateur fictif authentifié mais sans autorisation tenant/Run/HITL : attendre HTTP 503, zéro mutation. Avec authentification invalide, attendre refus avant toute I/O ; ne pas imposer 503 à cette branche.
4. Vérifier `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, CSP `frame-ancestors 'none'` sur chaque réponse. Vérifier qu'un corps JSON malformé ne déclenche pas de forwarding Copilot.
5. Recette fonctionnelle distincte, avec identités autorisées et environnement de test : comparer navigation, dashboard, Core/Twin/Runs, NOC, GLPI, Copilot, Evidence, visualisation, clavier, focus, erreurs, chargement et états UNKNOWN. Capturer horodatage UTC, acteur/tenant fictif, URL, code HTTP, hash de réponse expurgée, SHA source, digest image et contexte Docker. Ne pas classer un 503 ACL comme régression.
6. Pour chaque version historique v28/V145/fs1073/fs1051/fs621, exiger digest/commit/rapport daté avant de renseigner « avant ». Aucun rollback effectif.

## Incident #557 (secondaire)
La preuve fournie par l'opérateur indique Docker rootless `aiops` UID 1001, socket `/run/user/1001/docker.sock`, 87 conteneurs et 210 images. `sudo docker` interroge un autre démon ; zéro objet rootful n'est pas une perte de stockage. Cette preuve est historique et non un contrôle hôte frais. Ne pas reconstruire.

## Livraison et rollback
Document de recette uniquement ; aucun code runtime modifié. CI au commit exact à vérifier séparément. Rollback de cette proposition : fermer la PR Draft ou revert documentaire sur branche dédiée, sans toucher à main ou Debian. Coordination : issue #555 et `docs/ops/HANDOVER-AIOPS2-CURRENT.md` (mise à jour réservée au coordinateur si fichier absent de main).
