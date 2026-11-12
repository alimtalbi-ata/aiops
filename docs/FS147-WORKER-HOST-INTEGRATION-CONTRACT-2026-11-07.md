# FS147 — contrat d'intégration hôte (proposition, sans mutation)

Statut : **PROPOSÉ / NON QUALIFIÉ E2E**. Complément de [FS364](FS364-ARCHITECTURE-REPRISE-2026-11-06.md), pas un changement de contrat Core ou Portal. Périmètre : ticket GLPI 147, mode DEMO, /fs-lab uniquement, sans SAN.

## Frontières et responsabilités

- **Core (propriétaire Core)** : alloue durablement incident_id/run_id/evidence_id/ticket_id ; expose au Worker un adaptateur `claim_once(key)` atomique, durable et multi-processus. `True` signifie réservation effectivement acquise ; `False` signifie doublon **prouvé** ; réponse absente, type inattendu ou timeout = état indéterminé. La clé est le SHA-256 JSON compact de `[tenant_id,incident_id,run_id,ticket_id]`. Aucun changement d'API Core n'est implémenté ici.
- **Bridge (propriétaire intégration)** : authentifie l'appelant, autorise uniquement `df/du/ls` sur `/fs-lab`, fournit résultats structurés, codes retour, provenance `fs-lab-bridge-readonly`, `read_only=true`, `collected_at` UTC avec fuseau, `used_percent` fini entre 0 et 100, `evidence_id` non vide. Les preuves doivent être liées à tenant/actor/incident/run/ticket. Interdire commandes libres, chemins fournis par l'utilisateur et toute écriture.
- **Worker** : `run_fs147_strict` exige contrôles bridge + Policy stricts ; stop_auto, scope et claim avant observation ; pas de fallback permissif. Fenêtre fraîcheur : observation au plus 5 min ancienne, au plus 30 s future. Chaque étape reçoit le même request et evidence_id.
- **Analyst / Critic** : réponses attestées et corrélées ; Analyst fournit findings non vides ; Critic doit répondre PASS pour atteindre Policy. Refus, erreur ou réponse ambiguë bloque.
- **Policy (propriétaire Policy)** : attestation scoped et décision `PASS/SIMULATE` seulement pour diagnostic sans effet ; `EXECUTE` interdit. Aucune approbation historique du ticket 146 ne vaut pour 147.
- **Intégration / GLPI** : lecture/corrélation du ticket 147 existant ; pas de création de ticket, pas de statut RESOLVED ni de mutation GLPI dans ce flux.

## Erreurs et replay

`STOP_AUTO`, `INVALID_SCOPE`, `DUPLICATE_RUN`, `IDEMPOTENCY_UNAVAILABLE`, `INSUFFICIENT_OBSERVATION`, `STALE_OBSERVATION`, `INSUFFICIENT_ANALYSIS`, `CRITIC_REFUSED`, `POLICY_REFUSED`, `UNKNOWN_TIMEOUT`, `SERVICE_UNAVAILABLE` conduisent à un blocage ou absence d'effet ; **un timeout ne prouve pas l'échec distant**. Après claim consommé, ne jamais réexécuter le même run par simple retry : réconciliation Core en lecture seule et décision humaine explicite pour tout nouveau run. La sémantique de `NO_EFFECT` désigne l'absence de remédiation initiée par Worker, pas une preuve d'absence d'effet réseau externe.

## Qualification d'intégration à exécuter par les propriétaires

1. Capturer sur Debian, en lecture seule, le digest de l'image Worker, SHA du checkout hôte, branche GitHub et configuration réseau ; ne pas présumer leur égalité.
2. Avec un `run_id` réellement alloué par Core et ticket 147, obtenir la preuve authentifiée bridge (df/du/ls) puis tracer evidence_id identique dans Analyst, Critic et Policy ; vérifier provenance, horloge et ACL sans exposer de secrets.
3. Injecter : doublon concurrent inter-processus, ACK Core perdu après commit, observation absente/périmée, Critic REFUSE, Policy REFUSE/EXECUTE, timeout à chacune des quatre frontières, STOP_AUTO. Exiger aucun deuxième appel bridge pour le même run, aucune mutation lab/GLPI.
4. Réconcilier journaux Core/Worker/GLPI et traces réseau par le même run_id ; ne déclarer PASS E2E qu'avec preuves datées, sans SAN, sans résolution du ticket.

## État de preuve

| Couche | État |
| --- | --- |
| CODE | Contrats et tests Worker existants ; ce document est une proposition d'interface |
| CI | À vérifier sur SHA exact |
| HÔTE | Non vérifié dans cette proposition |
| EXÉCUTÉ | Pas de transport authentifié ni de test E2E prouvé |
| Gate | **NO_GO E2E** |

Ne pas toucher à `scripts/fs/fs1097_patch.py`, `scripts/fs/FS.1113-history-race-candidate-validation.sh`, aux contrats Core, ni à la production.
