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

Le gate vérifie aussi l'absence de références SAN/Twin dans les métadonnées imbriquées du ticket et du RUN, pas uniquement dans `payload` et `provenance`. Une corrélation valide ne doit pas être acceptée si ces métadonnées sont contaminées. Cette vérification est structurelle et n'atteste pas l'authenticité des mesures.

## Régression enveloppe Evidence (2026-11-06)

Le contrôle de non-contamination parcourt désormais **l'intégralité de l'objet Evidence**, y compris ses champs supplémentaires, ses clés et les listes imbriquées. Les tests négatifs couvrent une référence `ACME-SAN-FABRIC-A` dans `context.upstream`, un collecteur `Twin-Simulator` dans `collector_details` et une clé d'enveloppe portant l'identifiant SAN. Une provenance et un payload propres ne suffisent plus à accepter une enveloppe contaminée. Aucun accès réseau ni effet LIVE. Cette régression reste une qualification CODE/CI, non une preuve d'E2E sur SRV-DEB-05.

## Régression E2E supplémentaire — replay inter-RUN (2026-11-06)

Le contrat fixture-only `tests/test_fs147_e2e_chain_contract.py` vérifie maintenant qu'une Evidence valide pour RUN A / ticket 147 est refusée pour RUN B / ticket 147, et inversement. Un reçu distinct, lié à RUN B, est accepté seulement pour RUN B. Les variantes de source `Twin-Simulator` (casse/espaces), `filesystem-SAN-bridge` et `FILESYSTEM-TWIN-collector` sont refusées ; une liaison RUN au ticket 146 est refusée. Aucun identifiant de fixture n'est une preuve d'exécution.

Gates au moment de cette modification : CODE publié sur PR #431 ; CI du nouveau commit non attestée (aucun workflow PR retourné) ; HÔTE SRV-DEB-05 non vérifié ; EXÉCUTÉ E2E 147 non démontré. Il reste à établir, en lecture seule, le vrai RUN de 147 et sa nouvelle Evidence `/fs-lab`, puis les transitions Core/Worker/Temporal/Portal/GLPI. Aucun déploiement ni approbation HITL implicite.

## Régression aliases SAN/Twin génériques — 2026-11-06

Le test fixture-only refuse désormais aussi les tokens `SAN` et `Twin` délimités dans les métadonnées imbriquées (`SAN-bridge`, `twin_adapter`, `collector/SAN`, `TWIN`), sans rejeter un mot ordinaire tel que `sanity`. Cela comble le contournement par alias sans imposer un adaptateur SAN. Le test ne prouve ni l'authenticité de l'Evidence ni l'existence d'un RUN 147 réel. Exécuter `python3 -m unittest discover -s tests -p 'test_fs147_e2e_chain_contract.py' -v` au SHA exact ; conserver CI, HÔTE et EXÉCUTÉ séparés. Aucun déploiement, aucune mutation du lab et aucune approbation HITL.

## Qualification complémentaire des fixtures — 2026-11-06

Le contrat E2E teste explicitement le rejet de métriques non finies (`NaN`, `+Infinity`, `-Infinity`) et d'un alias SAN enfoui dans une métadonnée `tuple` du RUN. Le contrôle accepte toujours une fixture filesystem cohérente après retrait de cette contamination. Ces assertions sont **des tests négatifs source-only**, pas des observations de l'hôte. Elles ne créent ni RUN ni Evidence et ne changent pas le comportement de production.

CI : six workflows GitHub ont conclu `success` pour le SHA précédent `122b5e701f9898d423b9efec031b5326b4dc2daa`, dont « FS V28 Twin isolation (source-only) ». Cela ne qualifie **pas** les nouveaux tests avant exécution au SHA du dernier commit. HÔTE Debian : non vérifié. EXÉCUTÉ E2E 147 : non démontré. Aucune fusion ni mise en production.

## Régression conteneurs set/frozenset — 2026-11-06

Le scanner de non-contamination des métadonnées internes parcourt maintenant également les ensembles Python `set` et `frozenset` (en plus des dictionnaires, listes et tuples). Une référence `SAN-bridge` dissimulée dans `run.collectors` est refusée ; après retrait, la fixture filesystem cohérente est acceptée. Cette extension ne change aucun adaptateur ni le chemin de production ; les objets JSON réels n'emploient pas de sets. Twin SAN reste **non requis** pour GLPI 147 et `/fs-lab`.

Gate : CODE publié dans la PR #431 ; CI à qualifier au HEAD exact ; HÔTE SRV-DEB-05 non contrôlé ; EXÉCUTÉ E2E non prouvé sans RUN réel, Evidence nouvelle et transitions observées. Aucun déploiement, aucune mutation, aucune approbation simulée.
