# FS147 — contrat de qualification E2E read-only (proposition inter-rôles)

Date : 2026-11-08. Référence : `docs/FS364-ARCHITECTURE-REPRISE-2026-11-06.md`.
Statut : **PROPOSITION / NO_GO E2E**, pas une attestation d'exécution.
Périmètre Worker uniquement ; aucune modification des contrats Core, Portal FS1097/FS1113, GLPI ou Policy.

## Chaîne et responsabilité

`Core durable claim -> fs-lab bridge read-only -> Analyst -> Critic -> Policy -> résultat NO_EFFECT`.
Un unique `tenant_id, actor_id, incident_id, run_id, ticket_id=147, mode=DEMO` est propagé à chaque frontière.
`alert_fingerprint` et `evidence_id` sont conservés dans le journal de corrélation du propriétaire Core ;
le Worker vérifie `evidence_id` aux frontières Analyst/Critic/Policy.
Les transports doivent être authentifiés par le service hôte, avec ACL tenant/acteur, sans
réutilisation de validation du ticket 146. Le Worker ne crée ni ticket ni approbation.
Ne jamais présenter `NO_EFFECT` comme une résolution.

## Interfaces proposées (à valider par les propriétaires)

- **Core / Intégration** : réservation atomique durable de la clé SHA256 JSON
  `[tenant_id,incident_id,run_id,ticket_id]` ; réponse booléenne stricte.
  `True` signifie réservation acquise, `False` signifie doublon ;
  ambiguïté, timeout ou panne donnent `IDEMPOTENCY_UNAVAILABLE`, sans appel bridge.
  La reprise d'un run déjà réservé doit lire son état durable plutôt que réexécuter
  les appels ; aucune nouvelle clé pour contourner un timeout.
- **Bridge / Worker** : réponse corrélée, `source=fs-lab-bridge-readonly`,
  `commands=["df","du","ls"]`, `filesystem=/fs-lab`, `read_only=true`,
  `evidence_id` non vide, `collected_at` ISO-8601 avec fuseau,
  `used_percent` numérique fini entre 0 et 100 ; preuve d'origine authentifiée
  requise par l'adaptateur strict. Pas de SAN ni de commande mutante.
- **Analyst / Critic** : contexte de corrélation complet, `evidence_id` identique ;
  Analyst fournit une liste de constats non vides, Critic `state=PASS`
  sinon `CRITIC_REFUSED`. Les refus et réponses manquantes sont bloquants.
- **Policy / Twin** : vérification stricte d'attestation et de corrélation,
  décision admissible uniquement `state=PASS, decision=SIMULATE` ;
  les contradictions ou refus produisent `BLOCKED/NO_EFFECT`.
- **Portal / Intégration** : présentation séparée des observations réelles,
  des décisions simulées et des preuves manquantes ; aucune transition `RESOLVED`.

## Fraîcheur, délais et UNKNOWN

Observation âgée de -30 secondes à +5 minutes, contrôle avant Analyst et juste avant
Policy. Hors intervalle : `STALE_OBSERVATION`. Chaque transport hôte doit imposer
un délai fini configuré et enregistrer la frontière concernée, sans rejouer une
opération dont l'issue est inconnue. `TimeoutError` : `UNKNOWN_TIMEOUT` ;
autre exception : `SERVICE_UNAVAILABLE`. Ces codes ne prouvent pas l'absence
d'effet distant ; seul le périmètre Worker est garanti sans remédiation.

## Matrice de qualification à exécuter sur environnement isolé

| Cas | Injection / preuve | Attendu |
| --- | --- | --- |
| Corrélation | même run_id/ticket147/evidence_id à toutes les frontières | NO_EFFECT, resolved=false, traces horodatées |
| Double invocation | deux appels concurrents avec même clé | une seule réservation gagnante, au plus un appel bridge |
| Données insuffisantes | observation incomplète ou constats vides | BLOCKED, aucun appel en aval |
| Critic refuse | state != PASS | CRITIC_REFUSED, Policy non appelé |
| Policy refuse | décision != SIMULATE ou état != PASS | POLICY_REFUSED, aucune mutation |
| Timeout ambigu | timeout bridge/Analyst/Critic/Policy | UNKNOWN_TIMEOUT, aucune relance automatique |
| Reprise | run réservé après timeout | lecture d'état Core, pas de second effet |
| Fraîcheur | +5m01s ou horloge >30s dans le futur | STALE_OBSERVATION, Policy non appelé |
| Mauvais périmètre | ticket146, tenant/acteur/run divergents | BLOCKED, pas de réutilisation d'approbation |
| Transport réel | attestations authentifiées, identifiants traçables | preuve hôte distincte du PASS des mocks |

## Gate / preuves attendues

CODE : SHA exact du Worker et diff isolé.
CI : workflow, SHA, logs et résultats des tests FS147 explicitement nommés.
HÔTE : digest image Worker, commit déployé, ACL transport, mapping et journaux
corrélés (sans secret), en lecture seule.
EXÉCUTÉ : même `run_id` et `evidence_id` démontrés depuis bridge fs-lab
jusqu'à Policy et lien GLPI 147, plus tests négatifs sur services réels.
Si l'une de ces preuves manque : **NO_GO E2E**.
Aucun déploiement production, aucune suppression/truncate, aucun RESOLVED.
