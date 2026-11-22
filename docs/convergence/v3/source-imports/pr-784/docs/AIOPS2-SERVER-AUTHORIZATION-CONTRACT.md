# AIOps2 — contrat d'autorisation serveur (proposition bloquante)

Statut : **NON IMPLÉMENTÉ / NO-GO LIVE**. Ce document définit le contrat requis avant toute réouverture des lectures Core/Twin et des commandes DEMO. Il ne constitue ni une attestation d'identité, ni une permission.

## Constat vérifié dans le portail

- `/api/portal/bootstrap` et `/api/portal/components` acceptent un jeton lecteur partagé pour l'authentification, mais renvoient `503 TENANT_ACL_NOT_QUALIFIED` sans appeler Core/Twin ni exposer les liens de navigation.
- `/api/copilot` refuse le transfert de questions à un Copilot sans contrat de lecture tenant/Run.
- `/api/demo` vérifie le jeton opérateur puis refuse toute mutation Core avec `503 TENANT_ACL_NOT_QUALIFIED`.
- Les démonstrations AIOps2 calculées sont des projections synthétiques publiques en lecture seule, **pas** des attestations runtime.

## Contrat minimal à livrer côté autorité

L'autorité d'accès doit être **côté serveur**, indépendante des champs envoyés par le navigateur. Elle doit fournir une décision vérifiable contenant :

| Champ | Exigence |
| --- | --- |
| `subject_id` | Identité stable dérivée d'une session/identité authentifiée côté serveur, jamais d'un body client |
| `tenant_id` | Tenant autorisé, dérivé d'une relation serveur sujet→tenant |
| `run_id` | Identifiant du Run demandé, validé contre le tenant et l'autorité Core |
| `resource` | Ressource exacte, ex. `core.run`, `twin.impact`, `copilot.context`, `demo.command` |
| `action` | `read` ou `simulate`; aucune action `execute_live` |
| `decision` | `ALLOW` uniquement après toutes les vérifications, sinon `DENY` |
| `policy_version` et `evidence_id` | Version et référence auditables, liées à la décision |
| `expires_at` | Expiration courte, vérifiée côté serveur; refus si horloge/fraîcheur indéterminée |

**Ne pas** considérer un jeton partagé lecteur/opérateur, un `tenant_id` fourni par le client, une URL de navigation ou un `run_id` bien formé comme une autorisation. Les permissions doivent être réévaluées à chaque accès et appliquées aussi par Core/Twin, pas uniquement par le portail.

## Séquence d'intégration bloquée jusqu'aux preuves

1. Authentifier le sujet et valider signature, audience, expiration et révocation avec l'autorité d'identité choisie.
2. Résoudre tenant, Run et droits à partir de sources serveur fiables, puis comparer au tenant propriétaire du Run.
3. Appliquer la décision côté service source avant toute lecture ou mutation; réduire les champs exposés au strict nécessaire.
4. Journaliser le refus ou l'autorisation sans jeton ni donnée sensible; conserver une preuve corrélable à la requête.
5. Sur absence, conflit, délai dépassé, panne de l'autorité ou erreur de validation : **DENY**, réponse sans données tenant, `Cache-Control: no-store`.
6. Garder `live_remediation_authorized = false` indépendamment du résultat d'autorisation.

## Critères d'acceptation E2E à implémenter

- Acteur A du tenant T1 : lecture du Run R1 de T1 **autorisée** seulement avec une attestation serveur valide.
- Acteur A du tenant T1 : lecture du Run R2 de T2 **refusée**, sans existence ou métadonnées de R2 divulguées.
- Acteur B sans rôle opérateur : commande DEMO **refusée**, même avec un jeton lecteur valide.
- Autorité d'identité ou ACL indisponible, attestation expirée, signature/audience invalide, Run absent, tenant contradictoire : **refus avant tout appel à l'upstream**.
- Autorisation valide mais preuve Core/Twin manquante ou périmée : `UNKNOWN`, jamais un impact présenté comme vérifié.
- Rejeu des mêmes entrées et preuves : décisions déterministes, sans écriture LIVE.
- Le test doit utiliser une autorité factice contrôlée et des services Core/Twin factices **en laboratoire**, puis être requalifié sur un environnement d'intégration autorisé.

## Décision de livraison

Tant que l'autorité serveur et les tests positifs/négatifs multi-tenant ne sont pas présents : **conserver les réponses 503 fail-closed existantes**, ne pas exposer Core/Twin, ne pas activer DEMO, ne pas fusionner et ne pas déployer. Les tests synthétiques existants ne satisfont pas à eux seuls cette condition.
