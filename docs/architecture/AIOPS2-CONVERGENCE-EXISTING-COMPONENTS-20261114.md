# AIOPS2 — dossier de convergence des composants existants

Date: 2026-11-14
Base: `main` au démarrage de la branche de convergence
Statut: **inventaire technique / intégration non qualifiée / aucun accès production**

## Objectif plateforme

AIOPS2 doit corréler les signaux techniques, incidents, services métier et éléments CMDB/GLPI; construire un contexte de diagnostic avec preuves et provenance; proposer des décisions contrôlées via Policy/HITL; puis vérifier le résultat et conserver une piste d'audit. GLPI n'est pas un simple connecteur de tickets: il doit être corrélé au Run, Incident, tenant, entité et acteur sans élargir les permissions.

## Règle de convergence

Ne pas reconstruire OIDC, les associations tenant/acteur, les xrefs GLPI ni le Copilot. Réutiliser les composants existants par portage sélectif vers une branche unique issue de `main`. Les PR historiques sont des sources de code et de contrats, pas des preuves de déploiement ou d'intégration cumulative.

## Inventaire vérifié

| Source | Composants identifiés | Limite à préserver |
|---|---|---|
| PR #194, `feat/temporal-hitl-v1` | `app/shared/hitl_identity.py`: vérification OIDC RS256/JWKS, issuer/audience, durée, groupes immuables→rôles, MFA/auth_time; routes `app/core/hitl_identity.py` | Le simulateur est explicitement non-production. La présence de configuration OIDC ne prouve ni disponibilité IdP ni qualification opérationnelle. Ce code est lié à HITL et n'est pas encore démontré comme principal générique pour toutes les API. |
| PR #631, `integration/tenant-actor-read-boundary-guard-20261111` | migration `009_portal_tenant_actor_read_groundwork.sql`, `app/core/portal_tenant_runs.py`, tests SQL/HTTP/schema | La migration pose des grants et bindings mais ne donne pas d'accès par défaut. Le reader est un helper non exposé par endpoint; il exige un actor_id dérivé côté serveur. Les routes globales Core restent hors périmètre. |
| PR #246, `fix/core-actor-delegation-failclosed-20261101-0220` | `app/core/actor_resource_authz.py`, `app/core/itsm_xref.py`, préflight introspection OAuth2 et association ressource | Le module est explicitement préflight fail-closed: l'introspection n'est pas une ACL GLPI native; pas de décision ALLOW métier avant adaptateur GLPI natif qualifié. Branche divergée; porter des unités isolées. |
| PR #520, `feat/glpi-copilot-xref-guard-20261110` | `glpi_signed_xref_boundary.py`, `glpi_xref_hmac_verifier.py`, `glpi_xref_postgres_nonce.py`, `glpi_server_readonly_assembly.py`, lecteurs/transport read-only | Le boundary refuse si le verifier n'est pas injecté. L'assembly exige des callbacks serveur pour fetch d'événement, nonce, ACL acteur et ACL lecture, plus des identifiants de service distincts. Ce sont des points d'injection, pas des trust roots installées. |
| PR #192/#193 | Client REST GLPI, ticket→contexte Copilot, proposition HITL | L'ancienne route utilisait un bearer portail partagé et lisait le ticket avant d'avoir une ACL individuelle/native GLPI. Ne pas réactiver telle quelle. |
| PR #712 | Contrat local de scope Incident/GLPI et tests de refus | Objet local constructible, pas preuve d'identité. Garder comme garde de refus isolée seulement; ne pas l'exposer comme autorité. |

## État des branches comparé à main

Référence main observée: `48deddadf365ac8a7cf71c7067f1c6cd740c32b6`.

- PR #194: 825 commits ahead / 88 behind; 300 fichiers dans la comparaison. Aucun merge de branche.
- PR #246: 19 ahead / 40 behind; 58 fichiers. Portage sélectif.
- PR #520: 168 ahead / 2 behind; 40 fichiers. Portage sélectif.
- PR #631: 24 ahead / 2 behind; 10 fichiers. Base utile à rafraîchir et vérifier.
- PR #712: 4 ahead / 0 behind; 3 fichiers. Contrat isolé.

## Résultats CI des HEAD observés

- PR #520, HEAD `e41e570613e2243e353581c7ee93dce9525239ae`: 3 checks SUCCESS.
- PR #631, HEAD `2bd8cf4615f9fc185e74d43e91a0af5274f5a37e`: 5 checks SUCCESS.
- PR #712, HEAD `9bf73279bdec1fb097afd1106f25b2dc627fd2b1`: 3 checks SUCCESS.

Ces résultats sont des checks CI de HEAD indépendants. Ils ne qualifient pas leur intégration, un IdP configuré, un GLPI réel, l'ACL native ou le déploiement.

## Architecture cible à assembler

1. **Principal authentifié Core-owned**: valider issuer, signature/JWKS, audience, expiration, not-before, nonce/JTI/révocation, assurance et mapping versionné. Le sujet immuable est dérivé du couple issuer+subject. Aucun rôle/acteur/tenant issu du navigateur.
2. **Autorité d'appartenance**: résoudre les grants acteur→tenant actifs et leur révocation côté serveur/DB. Les bindings Run→tenant doivent être explicites; aucun backfill ou tenant par défaut.
3. **Autorité GLPI**: valider les droits natifs du compte/utilisateur GLPI sur l'instance, le profil, l'entité et le ticket/CI demandé. Le token d'application/service ne prouve pas le droit de l'acteur humain.
4. **Xref signée**: vérifier issuer/audience, signature, fenêtre temporelle, association unique active, nonce PostgreSQL atomique et liaison exacte tenant/instance/entity/ticket/incident/run.
5. **Read-only assembly**: injecter les trust roots et les callbacks depuis la configuration serveur; faire passer l'autorisation avant toute lecture upstream; séparer identité opérateur et credentials de service.
6. **Copilot / Analyst / Critic / Policy / HITL**: injecter le ticket comme donnée non fiable, garder la provenance, distinguer faits/hypothèses, produire une proposition plutôt qu'une action et préserver l'approbation humaine.
7. **Vérification indépendante**: comparer l'état post-action aux préconditions et postconditions; journaliser acteur, tenant, décision, preuves, version de policy et résultat.

## Gaps à qualifier avant endpoint positif

- Le provider OIDC réel et son issuer/JWKS/audience sont-ils configurés, joignables et testés par des assertions non simulées?
- Le vérificateur OIDC fournit-il un principal générique réutilisable par les routes Core, et comment JTI/révocation sont-ils traités?
- Qui provisionne et révoque les grants acteur/tenant et les bindings Run/tenant? Quelle preuve d'approbation et quel audit?
- Où est l'adaptateur qui vérifie les permissions natives GLPI du compte humain sur instance/profil/entité/ticket? Un compte de service GLPI seul ne suffit pas.
- Où résident l'événement xref signé, sa clé protégée et le consommateur nonce transactionnel? Sont-ils effectivement installés côté serveur?
- Les ACL s'appliquent-elles également aux incidents, preuves, CI/CMDB, vues Digital Twin et résultats Copilot, et pas seulement aux Runs?
- Les refus auth/tenant/entity/ticket/revocation/replay produisent-ils **zéro** appel réseau Core/GLPI et zéro donnée partielle?
- Les tests A/B utilisent-ils un PostgreSQL et un GLPI éphémères avec des permissions distinctes, sans secrets ni données de production?

## Séquence d'intégration proposée

A. Porter d'abord les tests et migration #631 dans une branche basée sur main; confirmer compatibilité du schéma et aucun endpoint global exposé.
B. Porter le vérificateur OIDC de #194 en isolant son code de simulation et en définissant un contrat de principal Core-owned; tests unitaires signature/issuer/audience/exp/nbf/amr/auth_time/group map.
C. Porter le préflight #246 et le contrat de ressource, en maintenant le résultat UNKNOWN/DENY tant que les droits natifs GLPI ne sont pas vérifiés.
D. Porter les primitives #520 et leurs tests: xref HMAC, nonce PG atomique, transport allowlist, assembly serveur read-only.
E. Ajouter l'adaptateur natif GLPI et les tests d'isolation A/B, puis seulement définir l'endpoint read-only positif.
F. Rebrancher le contexte ticket au Copilot avec provenance et protection contre prompt injection; aucune création/approbation/exécution implicite.
G. Qualification cumulative CI, puis environnement éphémère; revue sécurité avant toute opération sur Debian.

## Interdictions de cette branche

Pas de secret réel, pas de configuration d'IdP/GLPI de production, pas de fetch réel GLPI/Core, pas de migration live, pas de fusion automatique des anciennes branches, pas de déploiement Debian, pas d'écriture GLPI, pas d'approbation ni exécution LIVE.

**Statut: dossier de convergence seulement. Production NO-GO.**
