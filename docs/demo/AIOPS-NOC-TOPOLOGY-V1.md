# AIOps NOC — Topologie SAN et dépendances métiers (démonstration)

## Amélioration V1
Le tableau de bord HTML autonome `demo/noc_wallboard.py` visualise désormais une chaîne d'impact `SAN FC → stockage → VMware → hôte applicatif → ACME Payments` depuis les mêmes six événements multiconstructeurs RAG synthétiques.

La source `demo/noc_topology.py` fournit sept nœuds et six arêtes de dépendance typées : Brocade Fabric A, Cisco MDS Fabric B, FlashArray, PowerMax, ESXi, pay-api-01 et le service métier ACME Payments. Les états sont dérivés de `demo.noc_synthetic_snapshot`; aucune identité CMDB n'est inventée à partir d'un équipement réel.

## Exécution hors ligne
```bash
python -m demo.noc_wallboard --output /tmp/aiops-noc-topologie.html
```

La page autonome présente les états et les liens de dépendance, puis les tableaux hôtes, services et alertes existants, avec filtres par criticité. Elle marque clairement la topologie `CMDB SYNTHÉTIQUES`.

## Contrats de vérité
Le graphe `aiops-noc-synthetic-topology-v1` affirme expressément `live_discovery=false`, `cmdb_verified=false` et `live_remediation_authorized=false`. Une relation proposée pour illustrer le scénario ne prouve **pas** la topologie réelle de la stack ; elle ne peut pas justifier de remédiation, d'accès au SAN ou de modification GLPI. Les hôtes additionnels dans un snapshot de simulation sont autorisés, mais les six assets de référence restent obligatoires.

## Qualification et prochaines étapes
Quatre tests de non-régression contrôlent les sept nœuds, les six liens, l'affichage HTML, le rejet d'une fausse attestation live et les assets manquants. Le workflow `AIOps simulated NOC RAG corpus qualification` comprend ces nouveaux tests. Leur résultat doit être vérifié au SHA correspondant.

La prochaine étape est d'ajouter le drill-down de chaque incident, puis de remplacer progressivement les relations synthétiques par une CMDB récupérée et vérifiée, en lecture seule dans un environnement isolé. Garder la séparation historique Checkmk/Thruk, Grafana, GLPI, n8n et le portail `:17777` jusqu'à une intégration authentifiée.
