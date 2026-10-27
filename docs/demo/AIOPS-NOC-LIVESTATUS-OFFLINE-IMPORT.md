# AIOps NOC — Import Checkmk Livestatus (fichiers hors ligne)

**Statut : adaptation testable, aucune connexion au réseau ni aux conteneurs.**

La stack historique `aiops_noc` disposait de Checkmk Community 2.5 et de Thruk. Le collecteur `demo/noc_livestatus_import.py` traduit désormais une table déjà exportée Livestatus au format `name/state/plugin_output` en contrat normalisé `aiops-checkmk-offline-readonly-v1` à partir des contrôles existants de `demo/noc_checkmk_export.py`.

États numériques admis : 0=OK, 1=WARN, 2=CRIT, 3=UNKNOWN. Les colonnes non approuvées, états malformés (dont booléens), noms invalides, doublons et exports expirés sont rejetés. L'objet garde `transport=OFFLINE_LIVESTATUS_EXPORT`, `provenance=OPERATOR_EXPORT_UNVERIFIED`, `runtime_authenticated=false`, `live_remediation_authorized=false` : un export ne prouve ni sa session, ni la santé de Checkmk, ni celle de Thruk.

## Exemple unitaire simulé
```python
from demo.noc_livestatus_import import normalize_livestatus_hosts
rows=[{"name":"brocade-fc01","state":2,"plugin_output":"Synthetic example"}]
result=normalize_livestatus_hosts(rows,captured_at="2026-10-24T20:00:00Z",now_utc="2026-10-24T20:01:00Z")
assert result["hosts"]["brocade-fc01"]["state"]=="CRIT"
```

Quatre tests ciblés sont intégrés à `aiops-rag-ops-fixtures.yml`. Prochaine étape : ajouter un collecteur réseau isolé *strictement en lecture seule*, après audit de la configuration réelle, des permissions et de la sécurisation du transport ; la production Debian reste inchangée.
