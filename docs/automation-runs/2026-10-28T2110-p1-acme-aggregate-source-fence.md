# 2026-10-28 21:06–21:10 Europe/Paris — E2E/Evidence ACME, contrôle agrégé

## Base vérifiée, concurrence et périmètre
- HEAD `main` vérifié avant code : `b6cac31f6713d60f517bc6c4648002297fb87de6` ; revérifié avant ce journal : `b6cac31f6713d60f517bc6c4648002297fb87de6`.
- PR ouvertes et branches de livraison consultées : #133 (événements/cibles canoniques), #139 (trace NOC), #142 (Twin, impact **topologique**), #144 (gate Policy Core persistée), #143/#145 (Demo Studio V2 sur branche divergente), #128 (timeline Evidence), #121 (chaîne Evidence Studio), #146 (déploiement non activé). Les travaux ne sont pas fusionnés ici.
- Continuité consultée : `docs/PROJECT-CONTINUITY.md`, `docs/QUALIFICATION-AND-CHANGE-PROTOCOL.md`, `docs/automation-runs/2026-10-28T1914-p1-acme-readonly-qualification.md`, contrat #133 et contrat Core/Policy #144.
- Branche dédiée `test/p1-acme-aggregate-source-fence-20261028-2106` issue de `main` ; [PR draft #151](https://github.com/alimtalbi-ata/aiops/pull/151). Aucun déploiement, merge ni requête au serveur Debian.

## Micro-livraison mesurable
- Commit code/tests : [`e2f01bdc657826c4ca96807ee6b19bafb972d6f8`](https://github.com/alimtalbi-ata/aiops/commit/e2f01bdc657826c4ca96807ee6b19bafb972d6f8).
- Fichiers modifiés : `scripts/qualify_acme_readonly.py` et `tests/test_explore_story_playwright_e2e.py` ; présent journal ajouté séparément.
- Réemploi ciblé des neuf cibles `cue/service/view/expected_state` documentées en #133. Le validateur agrégé refuse une falsification **cohérente des deux projections** Impact et Story, pas seulement leur désaccord.
- Liaison stricte `simulation_ticket_id=SIM-GLPI-<12 premiers caractères SHA-256 en majuscules>` et provenance `SYNTHETIC_LABEL_NOT_A_GLPI_TICKET` ; contrôle de l'origine fixture/horloge, sans prétendre vérifier une horloge runtime.
- Analyst/Critic/Policy restent des hypothèses déterministes : refus de `provider` LLM fictif, d'une approbation Critic ou d'un état Analyst attesté.
- **Contrat API inchangé** : aucune nouvelle route ni écriture. Sortie `aiops.acme-readonly-qualification.v1` inchangée, `contract_status=PASS` limité au fixture, `overall=NO_GO` obligatoire. Aucun `evidence_id` promu en attestation.

## Tests et CI réellement observés
- [quality.yml PR #40760658172](https://github.com/alimtalbi-ata/aiops/actions/runs/40760658172), SHA **exact du code/tests** `e2f01bdc657826c4ca96807ee6b19bafb972d6f8` : **completed/success**, trois jobs SUCCESS (policy-and-static, Core/PostgreSQL éphémère, Grafana éphémère).
- Logs `policy-and-static` lus : **6/6 tests Chromium/FastAPI éphémère OK** (`Ran 6 tests in 2.753s`), dont `test_06_aggregate_rejects_joint_target_and_synthetic_id_forgery`. Falsifications faites sur copies de réponses HTTP réelles du portail éphémère, **pas** des observations des services amont.
- Tests Core/PostgreSQL et Grafana exécutés dans leurs jobs existants ; ils ne valident pas la chaîne métier ACME inter-services.
- CI du **commit documentaire final** : à revérifier après ce commit ; ne pas extrapoler le SUCCESS du commit code au HEAD final.
- Aucun test local supplémentaire exécuté, aucune preuve opérateur authentifiée.

## Matrice GO/NO-GO et risques
| Priorité | Qualification | Statut |
| --- | --- | --- |
| P0 | Portail FastAPI ↔ Chromium et contrat synthétique Impact/Story | PASS sur code SHA ci-dessus, **pas** E2E métier |
| P0 | IDs `run_id`, `incident_id`, ticket synthétique, cibles checkpoints | PASS sur fixture/contrat synthétique uniquement |
| P0 | Core → Temporal → Analyst/Critic → Policy → Evidence → Portal, mêmes IDs runtime | NOT_TESTED |
| P0 | `evidence_ids` corrélés à des reçus indépendants, captures opérateur authentifiées, revue confidentialité | NOT_TESTED |
| P0 | Twin SAN → Payments comme impact observé | NO_GO ; #142 démontre des candidats topologiques, pas une panne |
| P1 | Tenant ACL runtime/RBAC et lectures inter-services Core/GLPI/n8n/Thruk | NOT_TESTED |
| P1 | Vidéo client 10–12 minutes | NO_GO, parcours opérationnel incomplet |

- Risque principal : confusion entre le `SIM-ACME-...` du fixture et les sept runs DEMO rapportés sur Debian ; aucune liaison runtime vérifiée.
- Le reçu navigateur `CI_SIMULATED_PORTAL` est une observation UI locale non attestée, pas une preuve LIVE.
- La validation de cibles n'authentifie ni les événements, ni les sources, ni la chaîne Temporal/HITL ; l'intégrité SHA-256 ne vaut pas signature d'opérateur.
- Coordination transmise dans les conversations PR #133 et #143.

## Prochain micro-lot
Après convergence ciblée de #133, ajouter à la recette la lecture authentifiée de `GET /api/demo/acme-scenario` et tester l'égalité des `event_id`, `run_id`, `incident_id` et états **attendus**, en gardant `status=MISSING` et `overall=NO_GO` jusqu'à une liaison Evidence indépendante. Ne pas accéder au portail Debian, déclencher d'action LIVE ou produire de vidéo avant qualification.
