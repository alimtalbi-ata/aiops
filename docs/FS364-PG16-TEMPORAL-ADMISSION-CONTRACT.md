# FS.364 — contrat d'admission transactionnelle PG16 (proposition, non déployée)

Référence : [architecture de reprise](../../docs/FS364-ARCHITECTURE-REPRISE-2026-11-06.md). Ce document complète l'adaptateur SQLite de la PR #440 ; **aucun effet LIVE**, aucun GET GLPI exécuté, aucune reprise Temporal et aucune modification des images Debian.

## Identités et invariants

Le backend doit lier `(tenant_id, alert_fingerprint, incident_id, run_id, evidence_id, mode, glpi_ticket_id=147)` à une clé d'idempotence. `mode` appartient exclusivement à `DEMO` ou `LIVE`, est fixé à la première écriture et ne peut changer par rejeu. Un même incident peut avoir plusieurs runs : ne pas imposer `UNIQUE(incident_id)` à la table de runs. Le ticket 146, les identifiants vides, une evidence d'un autre run, un tenant contradictoire et un ticket inexistant sont refusés. Une demande identique renvoie la même liaison sans produire de nouvelle evidence, de nouveau run ni de ticket GLPI. Une demande différente avec la même clé est un conflit, pas un upsert silencieux.

L'adaptateur de référence ne crée jamais de ticket. Le backend de production effectue un **GET GLPI authentifié** du ticket 147 et valide type incident, référence `AIOPS2-REAL-FS-20261106`, tenant et appartenance incident via une source backend autoritative. Une réponse indisponible, périmée ou non attribuable refuse la liaison. Le booléen `fetched_from_glpi` seul n'est pas une preuve.

## Transaction PG16 / version autoritative

Proposition de transaction, à adapter au schéma réellement déployé et à tester en migration avant tout merge :

1. Vérifier OIDC, ACL tenant/acteur, STOP_AUTO et mode DEMO/LIVE ; ne jamais déduire l'autorisation d'un paramètre client.
2. Lire et vérifier GLPI 147 par backend authentifié ; enregistrer l'identifiant et la version/horodatage de cette observation. **Ne pas conserver une validation historique du ticket 146 comme approbation.**
3. Dans une transaction PG16, verrouiller la ligne de run autoritative (`SELECT ... FOR UPDATE`), vérifier `run_id`, `incident_id`, `tenant_id`, `mode`, `state='WAITING_HUMAN'` et `state_version` attendue. Verrouiller ou comparer la version de décision Policy et l'approbation native HITL ciblée (ticket 147, run, action, chemin, empreinte/taille, expiration, validateur distinct). Refuser `DENY`, `BLOCKED_NO_EFFECT`, `CREATED`, `RESOLVED`, approbation absente/expirée ou STOP_AUTO actif.
4. Insérer une ligne d'admission unique par `(tenant_id, run_id, state_version, request_id)` avec une contrainte d'unicité du **dispatch logique** par `(tenant_id, run_id, state_version)`. Les conflits de payload sont refusés ; le rejeu identique renvoie l'admission existante mais **ne redéclenche jamais le signal**.
5. Dans la même transaction, insérer un événement **outbox** unique portant le même identifiant d'admission et l'état `PENDING` ; commit. Ne jamais appeler Temporal à l'intérieur de la transaction SQL.
6. Un dispatcher autorisé revendique l'outbox avec `FOR UPDATE SKIP LOCKED`, revérifie les autorisations et la version d'état juste avant l'envoi, puis utilise un identifiant de signal idempotent et une déduplication côté workflow. Après crash, la livraison peut être *at least once* ; seule la déduplication de bout en bout empêche une reprise double. Une révocation entre commit et dispatch doit empêcher l'envoi.
7. Journaliser admission, refus, version Policy, version Temporal, vérification GLPI et accusé de réception. **Admission n'est pas exécution ni résolution.** Aucun changement de statut GLPI sans preuve réelle.

## Critères de tests obligatoires

- Double clic, rejeu après restart, concurrence multi-connexions et collision de clé : un seul événement outbox logique, aucune création GLPI.
- Revocation Policy/STOP_AUTO/HITL avant claim et entre claim et dispatch : zéro signal autorisé.
- Changement concurrent de `state_version` ou `mode`, evidence étrangère, tenant étranger, ticket 146, GET GLPI 404/timeout : refus fail-closed.
- Crash après commit avant dispatch, crash après signal avant ack, redelivery : pas de deuxième transition Temporal.
- DEMO ne peut devenir LIVE par rejeu ; LIVE exige autorisation distincte et n'est **jamais** déclenché par ces tests.
- Vérifier les SHA des images Core/Worker/Portal réellement actives sur Debian indépendamment du SHA GitHub ; préserver checkout dirty et overlays.

**Statut : contrat de conception seulement.** Pas de migration PG16 appliquée, pas de preuve E2E, pas de comparaison Debian. Gate de déploiement : **NO_GO**.
