# FS147 — exclusion Twin SAN et qualification E2E (2026-11-06)

Référence : [FS.364](FS364-ARCHITECTURE-REPRISE-2026-11-06.md). Incident GLPI **147**, filesystem **/fs-lab** sur conteneur lab isolé. **Twin SAN non requis** : aucune opération sur `ACME-SAN-FABRIC-A`, aucune mutation SAN, aucun adaptateur ni framework supplémentaire. La mesure doit provenir du lab (df/du/ls read-only), et non d'une simulation Twin.

## Régressions source-only

`python3 -m unittest discover -s tests -p 'test_fs147_e2e_chain_contract.py' -v`

Le contrat rejette la contamination SAN/Twin, la réutilisation d'une Evidence d'un autre RUN, les identifiants V28 historiques, une mesure absente/invalide, les incohérences ticket/RUN/Evidence et une empreinte d'alerte contradictoire. **Nouvelle régression :** une approbation historique GLPI 146 / TicketValidation 3 est rejetée même lorsqu'une mesure filesystem 147 valide est présente ; elle ne peut pas être blanchie par une Evidence récente. Une approbation 147 dans une fixture ne constitue **jamais** une autorisation d'exécuter une action.

## États de qualification

- **CODE** : tests/contrat présents sur la branche de PR #431 ; vérifier le SHA exact.
- **CI** : exiger un workflow vert sur ce même SHA ; ne pas transférer les résultats d'un commit antérieur.
- **HÔTE** : non qualifié sans vérification read-only sur SRV-DEB-05 du code actif, de Prometheus, du RUN réel et de son Evidence /fs-lab.
- **EXÉCUTÉ** : non démontré tant qu'un même `alert_fingerprint -> incident_id -> run_id -> evidence_id -> glpi_ticket_id=147` n'est pas attesté dans Core/Worker/Temporal/Portal/GLPI. Aucun RUN de fixture n'est un RUN réel.

STOP_AUTO, Policy, HITL et le ticket 146 restent intacts. Aucun merge, déploiement, suppression, truncate, approbation ou RESOLVED simulé. Toute remédiation exige une validation native ciblée et vérifiée côté backend.
