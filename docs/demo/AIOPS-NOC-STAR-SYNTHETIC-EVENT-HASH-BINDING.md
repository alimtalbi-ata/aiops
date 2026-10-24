# NOC AIOps — Liaison de neuf événements STAR synthétiques aux captures illustratives

Le module `demo/noc_star_event_binding.py` prend neuf événements de démonstration STAR dans l'ordre canonique (`detect`, `correlate`, `enrich`, `analyze`, `ticket`, `approve`, `simulate`, `verify`, `close`) et un index de captures NOC classées `OFFLINE_TEST`.

Pour chaque événement, il exige `source_type=SYNTHETIC`, un même couple `run_id`/`incident_id`, des `event_id` distincts et des identifiants bornés. Il produit une empreinte SHA-256 du contenu JSON canonique de chaque événement. Il associe les identifiants des événements aux captures uniquement selon la correspondance **illustrative** déjà documentée.

Le résultat `aiops-noc-synthetic-star-hash-link-v1` contient les neuf empreintes, trois associations de captures et les champs obligatoires `runtime_authenticated=false`, `verified_runtime_event_links=0`, `live_remediation_authorized=false`. Une empreinte du payload ne constitue pas une signature d'origine et ne prouve pas que l'événement a eu lieu dans la stack réelle.

Quatre tests vérifient le parcours nominal, le refus de runs/incidents mélangés, le refus d'une source prétendument réelle et le refus de l'ordre STAR erroné. Le workflow Chromium exécute ces tests ; le résultat du nouveau commit reste à qualifier.

**Suite :** distinguer un manifeste de simulation contrôlé d'une véritable chaîne d'identité événement→preuve attestée, puis relier le centre de preuves au portail de démo sans déployer sur le Debian existant.

## Renforcement : empreinte de l'association événement ↔ capture (25 octobre 2026)

Chaque entrée de `captures` contient désormais `synthetic_event_hashes` (couples
`event_id` / `event_sha256`) et `binding_sha256`. Cette dernière empreinte
est le SHA-256 du JSON UTF-8 canonique (clés triées, séparateurs compacts,
`allow_nan=false`) portant **ensemble** `run_id`, `incident_id`,
`capture_file`, `capture_sha256`, `illustrative_cues` et
`synthetic_events`. Les anciens champs sont conservés pour compatibilité.
Une modification d'un événement ou du SHA d'une capture change l'empreinte
de chacune de ses associations concernées. Les événements sont limités à
65 536 octets sérialisés et les identifiants à l'ASCII admissible.

**Contexte / patrimoine :** l'inventaire privé F20.13 du 15 octobre référence
`AIOps-UCP-F20.13-DEMO-MULTISTACK-KIT-v0.3/scripts/capture-multistack.py`
(SHA-256 `bc8fb46e81d37cb90f64d53feaa7e14171aa65e0137a0143650ba04d12e623ee`).
Ce collecteur Playwright historique utilisait des captures de vues sans
attestation suffisante des états métier. Son code reste en quarantaine ;
la correspondance actuelle est reconstruite **uniquement à partir de
métadonnées synthétiques vérifiées**, sans import ni navigation réseau.

**Architecture / interfaces :** `bind_synthetic_star_events(index, events)`
consomme l'index NOC `OFFLINE_TEST` et les neuf événements ordonnés ;
il produit un objet `aiops-noc-synthetic-star-hash-link-v1` enrichi.
Dépendances : `demo.noc_star_cue_map`, `demo.noc_evidence_center` et la
bibliothèque standard Python. Les empreintes ne sont **pas** des signatures,
n'attestent ni capture réelle, ni authentification, ni intégrité d'un système
externe, ni remédiation LIVE. Elles permettent seulement la comparaison
déterministe de fixtures de démonstration.

**Qualification :** `python -m unittest tests.test_noc_star_event_binding -v`
(avec dépendances du dépôt), puis workflow NOC/RAG GitHub Actions.
Tests ciblés : empreinte recalculée indépendamment, replay déterministe,
mutation d'événement, mutation de capture, refus Unicode et taille excessive.
Aucun accès Debian ou applicatif n'est nécessaire.

**Rollback :** rétablir les versions précédentes des trois fichiers
`demo/noc_star_event_binding.py`,
`tests/test_noc_star_event_binding.py` et du présent document
sur la branche de PR ; ne pas toucher `main`, aux conteneurs ou aux données.
Les consommateurs exigeant un schéma strict doivent accepter les deux
champs additionnels avant activation. Aucun déploiement n'est autorisé ici.
