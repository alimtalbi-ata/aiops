# AIOPS2 — recette différentielle Evidence / navigation / UX (2026-11-11 06:15 Europe/Paris)

## Périmètre et provenance
Audit d'upgrade, **pas** de reconstruction. Contrat source vérifié sur `main` : `app/portal/main.py` (blob `16d156c912ccc7592383f7d67a6a6a36fef50629`) inclut les routeurs NOC et GLPI, expose un shell HTML anonyme avec dashboard/runs/twin `UNKNOWN`, et refuse les lectures `/api/portal/bootstrap`, `/api/portal/components` et `POST /api/copilot` si ACL tenant non qualifiée. La source seule ne prouve pas le déploiement. L'historique v28/V145, les images fs1073/fs1051/fs621, l'actif port 7777 et le candidat port 17778 n'ont pas de correspondance commit/digest/HTTP attestée dans ce cycle : **UNKNOWN**.

## Matrice avant/après — à compléter uniquement sur preuves datées
| Capacité / route ou élément | Avant v28/V145/rollback | Après source main | Actif 7777 | Candidat 17778 | Cause probable si écart | Priorité | Stratégie |
|---|---|---|---|---|---|---|---|
| Shell `GET /`, navigation Runs/Twin/NOC/GLPI/Copilot | UNKNOWN | HTML anonyme ; états Core/Twin/Runs UNKNOWN ; navigation statique | UNKNOWN | UNKNOWN | lien/fragment cassé ou intégration masquée | P1 | corriger ancre ou rendu **sans** exposer URL tenant |
| Dashboard et Runs `GET /api/portal/bootstrap` | UNKNOWN | 503 UNKNOWN après viewer sans ACL qualifiée | UNKNOWN | UNKNOWN | absence de contrat tenant serveur, pas nécessairement régression | P0 sécurité | conserver fail-closed |
| Intégrations `GET /api/portal/components` | UNKNOWN | 503 UNKNOWN après viewer sans ACL qualifiée | UNKNOWN | UNKNOWN | navigation dynamique bloquée par ACL | P0 sécurité | conserver fail-closed |
| Copilot `POST /api/copilot` | UNKNOWN | 503 UNKNOWN après viewer sans ACL qualifiée | UNKNOWN | UNKNOWN | upstream non autorisé tenant/run | P0 sécurité | conserver fail-closed |
| NOC et GLPI (routeurs inclus) | UNKNOWN | Inclusion source attestée, HTTP non attesté | UNKNOWN | UNKNOWN | contrat endpoint/état vide/timeout divergent | P1 | correctif isolé après preuve |
| Evidence, visualisation, UX clavier | UNKNOWN | Contrat runtime non qualifié | UNKNOWN | UNKNOWN | perte d'accessibilité, provenance ou rendu | P1 | recette DOM + réponse expurgée |

## Scénarios de recette hors production (négatifs et fonctionnels)
1. Associer à chaque échantillon : horodatage UTC, commit SHA, digest image complet, version historique, contexte Docker, URL/route, code HTTP, type de réponse et empreinte SHA-256 d'une réponse expurgée. **Ne pas comparer les versions sans preuve de provenance**.
2. Shell anonyme : `GET /` doit préserver les états UNKNOWN pour dashboard/runs/twin, ne pas fabriquer de métriques ou incidents, ne pas contenir d'URL opérateur sensible. Tester liens, ancres uniques, focus clavier, contraste et petit écran ; toute perte est une régression UX candidate à confirmer.
3. Test négatif ACL : viewer fictif authentifié mais sans tenant/acteur qualifié, GET bootstrap/components et POST copilot doivent refuser (503, UNKNOWN, TENANT_ACL_NOT_QUALIFIED) **sans appel réseau amont**. Un refus voulu n'est pas une régression.
4. Test négatif Evidence : réponse vide, timeout ou provenance contradictoire doit rester explicitement UNKNOWN/non attestée, sans transformer une absence de preuve en succès ou en « healthy ». Comparer uniquement avec des fixtures synthétiques et le contrat effectif de la route une fois identifié.
5. NOC/GLPI : sur fixtures autorisées, distinguer absence de données, erreur HTTP, timeout et accès refusé ; ne jamais exécuter de mutation GLPI. Vérifier que les liens opérateur restent invisibles sans ACL.
6. Tester les en-têtes de non-cache et anti-embedding pour 200, 404, 405 et refus ACL. Aucune authentification réelle, aucun E2E prod, aucune mutation.
7. Reporter chaque divergence avec contrat attendu, observé, preuve, cause hypothétique, P0/P1/P2 et stratégie de correction testée ; pas de restauration de route ACL/HITL sans autorisation serveur.

## Statuts de preuve
- **SOURCE** : inspection GitHub du fichier précité, et inclusion de routeurs ; comportement live NON DÉMONTRÉ.
- **CI** : à qualifier sur SHA de cette PR ; ce protocole documentaire ne constitue pas un test exécuté.
- **DEBIAN UNKNOWN** : aucun nouvel accès hôte direct. Preuve historique opérateur rootless `aiops` UID 1001, socket `/run/user/1001/docker.sock`, 87 conteneurs/210 images ; `sudo docker` interroge le démon rootful distinct. Incident #557 = faux diagnostic, aucune récupération.
- **E2E NON VÉRIFIÉ**. Aucun rollback effectif.
- **Rollback GitHub** : fermer la PR Draft ou revert ce seul document sur sa branche ; ne toucher ni `main` ni Debian.
- **Handoff** : issue #555 ; `docs/ops/HANDOVER-AIOPS2-CURRENT.md` sur branche `docs/debian-deployment-qualification-plan-20261110` (pas sur main lors du contrôle). Le coordinateur peut synchroniser ce protocole sans collision.
