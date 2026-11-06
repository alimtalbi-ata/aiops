# FS.364 / ticket GLPI 147 — exclusion Twin SAN (source-only)

Référence: [FS364 architecture reprise](https://github.com/alimtalbi-ata/aiops/blob/main/docs/FS364-ARCHITECTURE-REPRISE-2026-11-06.md), datée 2026-11-06.

## Décision
Le lab filesystem 147 mesure un tmpfs `/fs-lab` dans `aiops2-fs-lab`; Twin SAN `ACME-SAN-FABRIC-A` n'est **pas** une dépendance de détection ni de diagnostic. Aucun événement Twin `SET_STATE`/`OBSERVE` SAN ne doit être produit par ce scénario. Le Worker doit lire une preuve filesystem réellement créée, liée au **nouveau** `run_id` et au ticket 147, et échouer fermé en l'absence de corrélation.

La PR #431 isole déjà `FS-DEBIAN-SYNTHETIC` des écritures SAN, mais sa validation exige encore `EVD-D2069BA816126499`, reçu historique V28 associé à `RUN-4FABD1786F107E51`. **Ces identifiants ne sont pas une preuve pour le ticket 147** et ne doivent pas être recyclés. Le run 147 n'est pas établi dans le document de reprise. Ne pas modifier cette validation par une simple constante `RUN-147` inventée.

## Régression livrée
`python3 -m unittest discover -s tests -p 'test_fs_v28_*.py' -v` inclut `test_fs_v28_lab147_non_contamination.py` : absence d'appels SAN dans la branche filesystem, refus du reçu V28 pour un autre run, refus d'une provenance Twin SAN. Ce sont des tests source-only, **pas** une qualification d'exécution Debian.

## Conditions d'intégration E2E
Avant d'activer le parcours lab147 : obtenir l'identifiant RUN effectivement créé pour le ticket 147; produire une Evidence de mesure `/fs-lab` (lecture seule, origine et horodatage vérifiables) corrélée à ce RUN et au ticket; vérifier le lien durable alerte→incident→run→evidence→GLPI 147; vérifier Worker/Temporal/Portal en mode DEMO avec Policy/STOP_AUTO, sans passer DGX_CRITIC par fabrication de HITL. Tester les refus mauvais run/ticket, preuve SAN, preuve absente, doublon, et validation historique du ticket 146. Ne jamais supprimer/tronquer le fichier du lab sans approbation native spécifique et vérifiée.

Aucune fusion ni déploiement impliqués par cette note. CODE/CI/HÔTE/EXÉCUTÉ sont des gates indépendants.

## Gate E2E de corrélation (fixtures, non exécuté sur hôte)

Le test `tests/test_fs147_e2e_chain_contract.py` exige ticket GLPI 147, nouveau RUN non historique, Evidence distincte du reçu V28, provenance portant le même RUN et ticket 147, mesure `/fs-lab`, horodatage et hash présents. Il rejette le ticket 146, un RUN divergent, une source Twin/SAN et une mesure d'un autre filesystem. Les identifiants `RUN-TEST-147` et `EVD-TEST-147` sont **uniquement des fixtures**, jamais des RUN/Evidence créés. Exécution locale proposée : `python3 -m unittest discover -s tests -p 'test_fs147_e2e_chain_contract.py' -v`. Ce gate ne fait aucun appel réseau, ne prouve aucune acquisition réelle et ne remplace pas la vérification backend/Temporal/Portal ni l'autorisation Policy/HITL.
