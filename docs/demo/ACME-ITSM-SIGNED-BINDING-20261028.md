# ACME P1 — contrat de liaison ITSM signé (2026-10-28)

**Statut : contrat pur, hors ligne, non raccordé au portail ni à GLPI.** La topologie SAN-FABRIC-A → HOST-ESX-01 → VM-PAY-01 → APP-PAY-01 et les incidents ACME-DEMO-SAN-001 / ACME-DEMO-PAY-002 restent des fixtures synthétiques.

## Entrées et frontière de confiance

`shared.acme_itsm_binding.correlate_acme_ticket` reçoit trois éléments indépendants : (1) le readback canonique DEMO de PR #85, (2) une observation de ticket issue du lecteur GLPI de PR #69, (3) un reçu de liaison **émis par une future autorité Core/ITSM**, signé HMAC-SHA256 avec une clé dédiée. L'appelant doit obtenir ces trois éléments par des adaptateurs authentifiés. **Un objet JSON fourni par un navigateur n'est jamais une observation GLPI authentifiée.**

Le reçu exact `aiops.acme-itsm-binding-receipt.v1` contient `issuer=CANONICAL_CORE_ITSMLINK`, `mode=DEMO`, `run_id`, `incident_id`, `ticket_id`, `entity_id`, `fixture_sha256`, `issued_at_utc`, `expires_at_utc`. La signature porte sur les **octets JSON exacts**, non sur une re-sérialisation. Le validateur rejette clés JSON dupliquées, champs supplémentaires, NaN, tailles excessives, clé trop courte, horloge non UTC, reçu expiré ou futur et observation GLPI périmée. Fenêtre maximale de validité : cinq minutes ; tolérance d'horloge future : trente secondes.

Une concordance stricte des identifiants, de l'entité GLPI et du hash du fixture retourne `CONTRACT_MATCHED_UNATTESTED`, jamais `LIVE` ni `runtime_attested=true`. Toute entrée absente, incohérente ou non authentifiée retourne `UNKNOWN` avec identifiants `null` (fail-closed). **La fonction ne vérifie pas à elle seule l'authenticité du transport Core/GLPI : celle-ci relève de l'appelant.** Aucun jeton de production n'est ajouté au dépôt.

## Limites et promotion

Le Core actuel n'émet pas de tels reçus ; aucun vrai GLPI n'a été interrogé ; aucun ticket réel n'est relié. Le test positif génère une signature **synthétique** avec une clé de test. Ce résultat prouve seulement le contrat local. La fonction n'est pas exposée en API publique et ne permet aucune écriture, remédiation, décision HITL ou promotion de l'état d'exécution Temporal.

Avant tout raccordement, implémenter un émetteur de reçu authentifié et borné côté Core, avec ACL par tenant, protection contre le rejeu, rotation des clés et audit ; qualifier le lecteur GLPI sur un vrai conteneur éphémère ; vérifier l'association indépendante du ticket dans le système d'enregistrement. Les PR #69/#73 et #80/#85 sont empilées et non fusionnées : résoudre leurs dépendances par portage ciblé, sans merge massif.

Tests : `python -m unittest discover -s tests -p test_acme_itsm_binding.py -v` (hors ligne). Le workflow existant `.github/workflows/quality.yml` exécute également ce test ; les résultats GitHub Actions doivent être consultés sur le HEAD final de la PR. **NOT_TESTED :** intégration réelle GLPI, Core/Temporal, n8n, Thruk, Debian, captures et vidéo finale.

Rollback : supprimer le module, ses tests et l'étape correspondante dans quality.yml ; aucune migration ni état runtime à restaurer.


## 2026-10-28 — verrou d'entité GLPI obligatoire (PR empilée sur #90)

Le vérificateur requiert maintenant `authorized_entity_id` (entier strict, plage 0..2147483647) dérivé **exclusivement** du contexte d'autorisation serveur de l'opérateur. Une valeur absente, booléenne, hors plage ou différente de l'entité signée et observée renvoie `UNKNOWN` sans identifiants. Un reçu valide, signé et cohérent avec une observation GLPI d'une **autre entité** ne traverse pas ce verrou. Le champ ne doit **jamais** être fourni tel quel par le navigateur ni calculé à partir du seul ticket ou du reçu. Les tests négatifs couvrent le rejeu inter-entités.

Ce verrou protège la sélection d'entité GLPI **au niveau du contrat** ; il ne remplace pas l'authentification de l'appelant, les ACL multi-tenant Core, la preuve de source GLPI, la qualification réseau ou la signature par un vrai émetteur Core. Les tests sont hors ligne, avec une clé et des observations synthétiques ; aucune preuve d'intégration réelle n'est revendiquée.

## 2026-10-28 — portée Run autorisée (PR empilée sur #96)

Le contrat exige `authorized_run_id` en plus de `authorized_entity_id`. Le Run autorisé doit provenir d'une ACL serveur liée à l'identité authentifiée, indépendamment du reçu signé, de la réponse Core et des paramètres navigateur. Une portée absente, invalide ou différente du Run canonique retourne `UNKNOWN` sans identifiants. Un reçu HMAC valable pour un autre Run de la même entité est rejeté. La réussite demeure `CONTRACT_MATCHED_UNATTESTED`.

**Non qualifié :** aucune authentification RBAC/Core réelle ni preuve de source GLPI ne sont apportées par ce contrat pur. La future API ne doit pas accepter `authorized_run_id` fourni par le navigateur. Aucun ticket GLPI réel, Temporal, LIVE ou déploiement n'est attesté.
