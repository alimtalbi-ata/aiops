# AIOps — API/écran d'impact ACME local (26 octobre 2026)

**Statut :** nouveau read model local et déterministe, non intégré aux backends et non qualifié en production.

## Besoin métier
Offrir depuis le portail existant une vue exploitable du scénario synthétique ACME SAN P1 → Payments P2, tout en exposant honnêtement les trous de preuve. Le besoin n'est pas de fabriquer un run, un ticket GLPI, un horodatage ou une capture. Cette vue complète les routeurs statiques existants sans introduire un second portail.

## Routes et interfaces
- `GET /api/demo/acme-impact` : JSON read-only avec `run_id`, incident source et impact, chemin de dépendances, SHA-256 de la source et champs manquants explicites.
- `GET /demo/acme-impact` : écran HTML local affichant les mêmes valeurs. Il ne contient ni script, ni formulaire, ni lien, ni appel réseau externe.
- Les deux routes sont montées sur `portal.main:app`. Aucun listener, port, worker ou tâche d'arrière-plan n'est ajouté.

## Architecture et provenance
Le contrôleur lit les octets exacts de `demo/integrations/v21315/acme-fixtures.json`, les passe à `load_fixture_bytes()` puis à `validate_fixture()` déjà existants, et calcule SHA-256 sur ces mêmes octets. Il réutilise donc le validateur du DAG plutôt que de recopier sa logique. Un identifiant `SIM-ACME-<16 hex>` est dérivé du digest : `run_id_provenance=DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN`. Ce n'est **pas** un identifiant Core/Temporal.

- `incident_id` = incident source synthétique SAN P1 ; `impact_incident_id` = incident cible Payments P2.
- `ticket_id=null`, provenance `ABSENT_NO_GLPI_WRITE` : aucun ticket n'est créé ni prétendu.
- `event_timestamp_utc=null`, provenance `ABSENT_NO_RUNTIME_EVENT` : aucun temps d'événement n'est inventé.
- `source_sha256` atteste l'identité des octets du fixture uniquement ; il n'atteste ni une capture, ni GLPI, ni n8n, ni Grafana, ni un runtime.
- `runtime_evidence_present=false`, `runtime_attested=false`, `production_qualified=false`, `live_remediation_authorized=false`.

## Dépendances et conditions de réutilisation
La route ne dépend que de FastAPI déjà utilisé par le portail et du validateur Python standard. Les chemins du fixture et du validateur sont constants, ne viennent pas de la requête HTTP et doivent être des fichiers réguliers non symlink. Si le fixture, le validateur ou le contrat manque/échoue, la route répond 503 avec un message générique ; aucun contenu partiel n'est rendu. La résolution du validateur est différée jusqu'à la requête afin qu'une image ne contenant pas les assets de démonstration puisse démarrer et refuser proprement cette vue.

## Tests
`tests/test_portal_acme_impact_read_model.py` vérifie l'unicité/méthode des routes, le SHA-256 lié aux mêmes octets que ceux validés, la répétabilité des réponses, les champs ticket/temps absents, les limites d'attestation, le refus 503 du fixture invalide/absent, l'encodage HTML, la CSP et le rejet des méthodes mutatrices. Le test du chargeur binaire vérifie également les clés JSON dupliquées et UTF-8 invalide. CI sur données locales uniquement.

## Historique et garde-fous
Le validateur et le fixture ACME sont déjà inventoriés dans `docs/recovery/HISTORICAL-CODE-REGISTRY-20261023.md` et `docs/recovery/OCTOBER-2026-ARCHIVE-CONTEXT-AND-REUSE.md`. Aucun ZIP original, secret ou extrait tronqué n'est réimporté ou déclaré complet par ce changement.

## Qualification, déploiement et rollback
Ce patch ne contacte aucun service et ne change aucune donnée. Il n'a été soumis qu'à la branche de PR. La restauration/annulation consiste à revert les commits du changement puis relancer les workflows ciblés ; aucune sauvegarde de base, intervention Debian, ouverture de port ou opération sur conteneur n'est nécessaire pour ce changement. **E2E runtime et production restent non qualifiés** jusqu'à une intégration authentifiée distincte, à des tests navigateur sur les vrais écrans autorisés, à des preuves indépendantes et à une approbation humaine de bascule.
