# AIOps NOC — Correction de corrélation et export Checkmk isolé

## Correction d'une défaillance réelle de CI
Le workflow `AIOps simulated NOC RAG corpus qualification` du commit `7212d5a` a échoué sur `test_mismatched_corpus_rejected` : une alerte pouvait référencer un équipement qui ne figurait dans aucun nœud de la topologie ; le drill-down l'ignorait et continuait silencieusement. Le module `demo/noc_drilldown.py` rejette désormais toute alerte à `asset_id` orphelin **avant** de fabriquer les diagnostics, conformément au test existant. Ne pas annoncer le succès avant la nouvelle CI.

## Adaptateur d'import offline Checkmk
`demo/noc_checkmk_export.py` reçoit un export JSON typé `aiops-checkmk-host-export-v1` rédigé/validé par un opérateur dans un environnement isolé. Il valide `source=CHECKMK_EXPORT`, lecture seule, noms de machines, états numériques 0/1/2/3, taille des sorties, unicité, horodatage UTC strict et délai de fraîcheur (300 secondes par défaut).

Il convertit les états en `OK/WARN/CRIT/UNKNOWN`, mais son résultat porte **toujours** `provenance=OPERATOR_EXPORT_UNVERIFIED` et `runtime_authenticated=false`. Il ne contacte pas Thruk, Checkmk, Livestatus ou Debian ; il n'intègre pas encore de capture authentifiée ni d'état de service. Le temps `now_utc` est imposé par l'appelant et sert seulement au calcul de fraîcheur, sans constituer une attestation.

### Exemple fictif (non extrait d'un vrai Checkmk)
```json
{
  "schema":"aiops-checkmk-host-export-v1",
  "source":"CHECKMK_EXPORT",
  "read_only":true,
  "live_remediation_authorized":false,
  "captured_at":"2026-10-24T20:00:00Z",
  "hosts":[{"name":"brocade-fc01","state":2,"output":"Synthetic test export"}]
}
```

### Tests et suites
Les nouveaux tests ciblent la détection des états critiques, un export expiré ou futur, les assets dupliqués et les revendications d'action LIVE. Les tests de cohérence du drill-down existants exécutent la régression exacte qui échouait. Workflow : `.github/workflows/aiops-rag-ops-fixtures.yml`.

La prochaine itération doit bâtir un collecteur Checkmk **lecture seule**, uniquement sur environnement d'intégration, puis le réconcilier avec un vrai inventaire CMDB et les preuves de capture. Les volumes historiques `/home/aiops/aiops-v1/stack/noc` restent inchangés.
