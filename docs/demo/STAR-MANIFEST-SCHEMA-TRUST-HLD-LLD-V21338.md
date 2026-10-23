# ACME STAR V2.13.38 — fail-closed deep-link provenance (23 octobre 2026)

## Périmètre et état

Correctif hors ligne uniquement : `demo/star_browser_manifest_gate.py`, tests adversariaux et cette note. Aucune capture runtime, aucun changement Debian, aucune importation n8n/GLPI/Grafana, aucun port publié. PR #36 conservée en draft ; `main` inchangée.

## HLD — frontière de confiance

Identités canoniques indépendantes (`run_id`, `correlation_id`, `event_ref`) → manifeste navigateur **non fiable** → analyse JSON stricte → liaison du deep link expurgé au service attendu → contrat d'horodatage → vérification PNG/CRC/SHA-256 et chronologie → revue humaine. Une image intègre n'authentifie ni la page runtime, ni la réussite métier, ni une validation HITL.

## LLD — invariants V2.13.38

- `source_url_redacted` et `event_time_alignment` sont désormais **obligatoires** ; leur absence bloque la preuve.
- Liaison par service : Grafana dashboard pour `detect/verify` ; n8n execution pour `correlate/enrich/analyze/simulate` ; GLPI V1 ticket pour `ticket/approve/close`. Un gabarit GLPI valide ne peut jamais qualifier une scène Grafana.
- L'alignement temporel reste `UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP` tant qu'une source indépendante n'a pas confirmé l'heure exacte de l'événement.
- Les clés JSON dupliquées sont rejetées, même lorsqu'une seconde valeur semble valide ; le parseur ne peut plus masquer une première valeur malveillante.
- Maintien des refus pour identités manquantes/contradictoires, attestations runtime/métier/HITL/LIVE, réutilisation d'image, chemins dangereux et CRC/SHA incorrects.

## Qualification et limitations

Commande : `AIOPS_STAR_NO_RUNTIME=1 python -m unittest discover -s tests -p 'test_star_*.py' -q`.

Tests locaux effectués sur le candidat cumulatif hors ligne, à distinguer de la CI du commit GitHub exact. Chromium utilisé uniquement sur fixtures synthétiques. **Aucune capture authentique** du portail :17777, de n8n, de Grafana ou de GLPI V1 :8080 n'est revendiquée.

Le `runtime-e2e` GitHub du 23 octobre (run 39955861031) reste en échec après le démarrage d'un run Temporal synthétique. La réussite technique n8n n'est pas une réussite métier. Ne pas assouplir Policy pour faire passer le test.

## Reprise, rollback et prochaines étapes

Revert ciblé des commits V2.13.38 sur la branche de PR si régression ; aucune intervention de production requise. Intégrer ensuite l'adaptateur Chromium lecture seule depuis le candidat offline, valider les liens exacts et les horodatages contre des événements indépendants, puis diagnostiquer la chaîne V1 02 Webhook → RAG → Canonical Identity → Call Analyst → 03 Prepare Analyst Payload (`RUN_ID_MISSING`) sur exports expurgés. Ne jamais fabriquer l'identité en aval. Aucun redémarrage du bridge V1.