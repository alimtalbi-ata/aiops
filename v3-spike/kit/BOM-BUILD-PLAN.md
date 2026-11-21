# AIOPS-V3 kit — BOM technique et plan de build (qualification en attente)

Statut: **DRAFT / NO-GO release**. Portée: serveur **neuf** seulement. Debian stable + Docker Engine/Compose plugin est une hypothèse d'architecture, **non validée sur hôte**. Ce document ne certifie aucune licence, provenance, image ou déploiement.

## Inventaire vérifié sur la branche d'intégration

| Élément | Source | Qualification |
| --- | --- | --- |
| Compose canonique | `v3-spike/kit/docker-compose.yml` | Trois services synthétiques gamma/core/demo, **pas** une distribution entreprise |
| Préflight statique | `v3-spike/kit/preflight.py` | Contrôles de profils source et de Compose JSON; tests et CI à attester |
| Tests kit | `v3-spike/kit/test_preflight.py` | 6 méthodes unittest, pas de preuve clean install |
| Data/event SQLite | `v3-spike/contracts/event_store.py` | 17 méthodes synthétiques, persistance de test |
| Frontière de sécurité | `v3-spike/contracts/secure_boundary.py` | 9 méthodes synthétiques; ni IAM ni ACL backend produit |
| GAMMA | `v3-spike/ux/test_gamma.py` | 5 méthodes navigateur synthétiques |
| CI | `.github/workflows/v3-spike-qualification.yml` | Six jobs (SQLite 17, sécurité 9, GAMMA 5, kit 6, resource-binding 6 + authenticated-binding 4 + pair-decision 5 + pair-decision 5, Compose default/DEMO); vérifier run ID/job ID/logs/UTC avant PASS |
| Liaison Event/Twin/Evidence | `v3-spike/contracts/resource_binding.py` | 6 méthodes synthétiques, 4 tests d'intégration authentifiée et 5 tests de décision appariée; Event v1 lie explicitement `twin_identifier` et `evidence_identifier`, mais aucune ACL ni association CMDB attestée |

**Manques bloquants** : Core produit, Temporal, Worker, Policy, HITL, Evidence, intégrations systèmes/stockage/réseau/applications/terminaux/cloud, workflows ITIL 4, installateur unique, migrations, sauvegarde/restauration, upgrade/rollback, secrets locaux, SBOM, signature, release, licence/provenance des dépendances et tests d'installation vierge. La présence ou réutilisabilité dans les autres dépôts n'est **pas attestée** par cet inventaire.

## État de qualification au 2026-11-21 (UTC)

Six jobs sont définis dans le workflow; cela prouve seulement la **présence du code CI**. Aucune exécution PASS n'est attestée par un run ID, un job ID numérique et des logs horodatés. La consultation des runs au SHA `16ade3487a3c600239e8cbcf7e055492fef904da` retourne `[]` via une interface **limitée aux événements pull_request**; ce résultat ne permet aucune conclusion sur les événements push. Tests Python exact-source, Chromium, `docker compose config`, installation vierge et redémarrage: **NOT_ATTESTED / NOT_RUN**. La validation indépendante D du contrat de substitution reste nécessaire.

## BOM OCI: aucune image produit approuvée

| Rôle | Référence actuelle | Digest OCI réel | Licence/provenance | Usage |
| --- | --- | --- | --- | --- |
| GAMMA | `GAMMA_IMAGE` | NON FOURNI | NON VÉRIFIÉ | fixture uniquement |
| Core | `CORE_IMAGE` | NON FOURNI | NON VÉRIFIÉ | fixture uniquement |
| DEMO | `DEMO_IMAGE` (repli `CORE_IMAGE`) | NON FOURNI | NON VÉRIFIÉ | fixture uniquement |

Les chaînes `fixture/*@sha256:aaaa…` du workflow sont **syntaxiques** et ne prouvent ni existence d'image ni digest de registre. Interdire leur promotion en release. Pour chaque image réelle: registre/repository, digest `sha256` résolu, architecture, Dockerfile/source commit, base image digest, licence SPDX et avis de provenance, SBOM CycloneDX/SPDX, analyse vulnérabilités, signature et attestation SLSA, dates UTC, liens de jobs et résultats. Refuser une licence inconnue ou incompatible.

## Séquence de build reproductible proposée (non exécutée)

1. Inventorier `aiops`, `AIOPS_GAMMA`, `aiops-debian-rebuild-private`, `aiops-debian-audit`, `observability-stack` et autres sources accessibles: commit exact, chemin, licence, provenance, secret scan, dépendances; `recovery-data` **métadonnées uniquement**. Réutilisation après revue, jamais copie aveugle.
2. Définir les contrats Core/Temporal/Worker/Policy/HITL/Evidence, la matrice de ports/volumes/réseaux, l'authentification, le modèle de secrets et les profils DEMO/entreprise/intégrations. Un **seul** `docker-compose.yml` canonique; aucun override requis.
3. Construire des images multi-architecture sur runner éphémère avec base/dépendances épinglées, provenance et SBOM; scanner, signer, publier des digests immuables. Générer un manifeste BOM versionné et contrôlé.
4. Implémenter l'installateur **unique** `preflight/install/health/upgrade/rollback/backup/restore`: chemins dédiés, idempotence, contrôle d'espace/OS/Compose, secrets locaux hors Git, migrations transactionnelles, snapshot préalable et rollback testé.
5. Sur VM Debian stable **neuve et jetable**: `docker compose config` profils default/DEMO/entreprise, clean install, health, restart, idempotence, upgrade, rollback, backup/restore, ports, volumes, isolation, absence de conteneurs superflus, E2E synthétique. Aucun accès aux hôtes existants.
6. Gates de release: preuves de jobs SHA/run/job numérique/log UTC, contre-revue D indépendante, SBOM/provenance/signatures, matrice de conformité, publication RC seulement après PASS. CENTRAL arbitre; `#831` est le registre, `#835` le suivi C. `#803` reste ouvert.

**Décision actuelle**: GO développement isolé; **NO-GO** installation/production/release. Ne pas toucher LIVE, main, INT07 #818/#829, ports 7770/7777/7790, Debian/cron ou hôtes existants.
