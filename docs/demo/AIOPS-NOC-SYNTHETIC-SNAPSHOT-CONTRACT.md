# NOC — Snapshot déterministe multiconstructeurs pour la démonstration

**Statut : fonctionnalité synthétique hors ligne.** Réutilise le corpus `demo/rag_ops_fixture_catalog.json` déjà versionné pour générer des états d'hôtes, alertes et impact sur les services métiers, sans créer une seconde stack de monitoring.

## Fonctionnement
Le module `demo/noc_synthetic_snapshot.py` produit `aiops-noc-synthetic-snapshot-v1` avec la même identité de run, des objets `hosts`, `business_services`, `alerts` et des totaux. Les six cas Brocade, Cisco MDS, Dell EMC PowerMax, Pure FlashArray, VMware ESXi et RHEL sont reliés à `ACME Payments`. Une table explicite `SEVERITY_BY_EVENT` fixe les états de démonstration ; rien n'est inféré de commandes d'un fabricant ni d'une vraie trap SNMP. Plusieurs alertes pour le même service sont consolidées vers l'état le plus grave.

Exécution hors ligne :

```bash
python -m demo.noc_synthetic_snapshot > /tmp/aiops-noc-synthetic.json
```

Le résultat porte `provenance=SYNTHETIC_SIMULATION_ONLY`, `checkmk_live=false`, `thruk_live=false`, `runtime_authenticated=false` et `live_remediation_authorized=false`. Il permet de développer le **mur NOC**, la topologie d'impact Payments et la timeline STAR avec une seule source d'événements déterministe. Il ne réalise **aucun** appel à Checkmk, Thruk, Grafana, GLPI ou n8n.

## Contrôles et exploitation
`tests/test_noc_synthetic_snapshot.py` valide les totaux, la consolidation du niveau CRIT de Payments, le déterminisme, le refus d'événements inconnus et de sources prétendument officielles, et l'identité de run. `.github/workflows/aiops-rag-ops-fixtures.yml` exécute ces tests. Contrôler sa conclusion au SHA actuel avant de revendiquer une qualification.

Prochaine étape prioritaire : construire une représentation NOC interactive de ce document, puis les adaptateurs **lecture seule** Checkmk/Thruk sur un environnement de test isolé. Reprendre les archives `/home/aiops/aiops-v1/stack/noc` avant toute réinstallation ; préserver ports, volumes et services de production. Les images/snapshots de test sont étiquetées synthétiques et ne remplacent jamais les captures de pages réelles.
