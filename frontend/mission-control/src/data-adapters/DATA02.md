# DATA02 — proposition normative B, soumise à arbitrage CENTRAL

Base B 368f430b05cc3df795e8e1d3d1fc8af8605cfec1 ; proposition A 949950281083d583e9f5efcc53ab503b36f32f24. Aucun export ni changement API avant arbitrage.

## Contrat proposé
Enveloppe additive versionnée `aiops.mission-data.view.v2` : mode PLATFORM/DEMO/OPERATIONAL ; state AVAILABLE ou UNKNOWN ; data T si AVAILABLE, null si UNKNOWN ; reason null si AVAILABLE, code explicite sinon. Provenance obligatoire par dataset, et par valeur si sources mixtes : origin SYNTHETIC/OBSERVED/UNKNOWN, domain PLATFORM_TECHNICAL/PLATFORM_AGGREGATE/BUSINESS/UNKNOWN, source identifiant fixe, source_sha256 nullable, observed_at/evaluated_at/retrieved_at epoch UTC secondes ou null, freshness FRESH/STALE/UNKNOWN, tenant_acl_qualified et runtime_attested explicites. Ajouter coverage {observed,expected,ratio} nullable ; expected > 0, 0 <= observed <= expected, ratio=observed/expected. Pour séries mixtes couverture globale calculée par somme des points attendus/observés, pas moyenne non pondérée. Ne pas modifier le calcul v1 existant. Toute conversion v1 conserve classification et erreurs ; champ absent UNKNOWN/null, flags absents false. AVAILABLE signifie lecture disponible, pas attestation métier.

## Règles obligatoires
- PLATFORM_TECHNICAL : up, scrape-duration (secondes), scrape-samples (nombre), six jobs applicatifs ; distinct des sept cibles runtime. Evaluation Prometheus != collecte; observed_at null. retrieved_at ne prouve aucune fraîcheur source. Sans horodatage observation et seuil approuvé par source, freshness UNKNOWN. Aucun P95 déduit du scrape.
- PLATFORM_AGGREGATE : catalogue B fixe, non partitionné ; grants restent vides. Refus AGGREGATE_AUTHORIZATION_NOT_QUALIFIED, jamais zéro ni liste vide. Ne pas assimiler agrégat à métier tenant. Pas de nouvel accès.
- BUSINESS : ACL serveur acteur/tenant et provenance requises avant restitution réelle ; sinon UNKNOWN/TENANT_ACL_NOT_QUALIFIED. Liste vide seulement après lecture exhaustive qualifiée pour le périmètre fixé ; pagination incomplète explicitement distinguée. Null != 0 ; absence de point != DOWN ; doublons ambigus rejetés, pas de somme implicite.
- DEMO : SYNTHETIC_SIMULATION_ONLY, source digest fixture, observed_at null, runtime_attested false, aucune autorité LIVE. OPERATIONAL interdit toute provenance SYNTHETIC même si réponse mal étiquetée ; PLATFORM uniquement dans panneaux techniques/agrégats explicitement classés. Pas de fallback, vider résultats au changement mode/contexte, ignorer réponses tardives.
- Identité EvidenceLink : incident_id/run_id/source_sha256 provenant du même snapshot, evidence_id et receipt_sha256 distincts et nullable. Digest source != reçu. Aucun rapprochement par libellé. Comparaison hypothétique séparée de l'état observé. C valide identité et digests ; aucun changement simulation.
- Temporal/GLPI : UNKNOWN runtime, GLPI handoff NOT_INSTALLED, aucune déduction depuis Worker UP ou lien natif ; aucun appel D03 réel sans GO et ACL/audit. Ne pas exposer historique brut.

## Recette D03 proposée (mock, NOT_RUN)
1. zero et null; trous et doublons; couverture 0, partielle, complète et ratio incohérent.
2. refus vs liste vide autorisée ; pagination non exhaustive ; absence ACL ; provenance manquante.
3. observed_at absent malgré evaluated_at/retrieved_at ; dates UTC ; stale et seuil inconnu.
4. contamination SYNTHETIC en OPERATIONAL, retour mode et réponse tardive ; aucune fuite de secrets.
5. tuple incident/run/source divergent, digest reçu distinct ; aucun lien implicite.
6. KPI métier non qualifié, grants vides, aucune substitution technique ou simulation.
7. Temporal/GLPI UNKNOWN et NOT_INSTALLED préservés ; aucun appel externe.

## Arbitrages requis
CENTRAL : schéma/version et compat v1; politique de fraîcheur et ACL. A : projection provenance par valeur, rendu refus/vide et couverture. C : identité canonique et preuve. D : fixtures négatives et audit. B : adaptateurs après arbitrage. Pas de runtime, build, test ou déploiement dans cette livraison documentaire.
