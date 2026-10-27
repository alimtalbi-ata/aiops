# NOC — RAG DEMO sourcé, strictement synthétique (2026-10-27)

Ce micro-lot réutilise **exactement le catalogue de six fiches** `demo/rag_ops_fixture_catalog.json` de la PR #36 (blob source `56b8a58faf9c2140d212686ef14313576904f0b5`) en le portant sous `app/portal/fixtures/noc_rag_synthetic.json`. Le validateur de la PR #36 a été adapté dans `app/portal/noc_demo_rag.py` : schéma strict, marqueur `SYNTHETIC_SIMULATION_ONLY`, échantillons `DEMO ONLY:`, références uniques, taille bornée, clés JSON dupliquées rejetées et hash SHA-256 des octets du catalogue et de chaque fiche.

## Parcours opérateur

Depuis le portail unique, panneau NOC : saisir le jeton de lecture `AIOPS_PORTAL_READ_TOKEN`, sélectionner l'équipement fictif (ex. `brocade-fc01`) puis **Lire fiches RAG DEMO**. Le navigateur appelle uniquement `GET /api/noc/demo-rag?asset=...` avec un header Authorization ; le jeton est vidé du champ, jamais placé dans l'URL ni stocké. L'API répond `SYNTHETIC_REFERENCE_ONLY` avec les identifiants et hash des fiches correspondantes, ou `UNKNOWN` sans citation si aucun équipement ne correspond. Les erreurs de catalogue donnent HTTP 503, les erreurs d'authentification HTTP 401/503. Les réponses sont non cacheables.

**Ceci n'est pas du RAG observé ni de l'IA exécutée.** Les labels Brocade, Cisco, Dell, VMware, Red Hat et Pure Storage sont des libellés fictifs, pas des citations de documentation constructeur authentifiée. Le catalogue n'est lié ni à une alerte Checkmk/Thruk observée, ni à un Run canonique, ni à Grafana, ni à NVIDIA NIM/Ollama. `llm_inference_performed=false`, `source_runtime_observed=false`, `tenant_acl_qualified=false`, `live_remediation_authorized=false` restent explicites. L'API est lecture seule, sans appel à un modèle, sans écriture et sans action LIVE.

**Sécurité et ACL :** le jeton opérateur existant est partagé, pas tenant-scoped ; l'isolation ACL multitenant est **NOT_IMPLEMENTED**. Ce panneau ne retourne donc que des fixtures synthétiques incluses dans le dépôt. Aucun document privé ni événement réel ne peut y être interrogé. Un futur RAG réel devra appliquer l'ACL du tenant avant la recherche, puis avant la citation, avec preuves de provenance, fraîcheur et lien Incident/Run.

## Tests et qualification

`python -m unittest discover -s tests -p test_noc_demo_rag.py -v` — 11 tests de contrat/erreurs, dont auth refusée, source absente, données fausses ou mal formées, identité d'asset, citations exactes et rejet de prétention LIVE. Réutilisation de `.github/workflows/quality.yml` pour CI. **Ce ne sont pas des tests d'intégration Checkmk/Thruk, Grafana, Core ou NIM** ; ces composants restent `NOT_TESTED` dans ce lot. Aucune capture Debian, preuve LIVE ou qualification de qualité 192B n'est revendiquée.

Prochain micro-lot : fournisseur Checkmk/Thruk réellement exécuté dans des conteneurs CI isolés ; projection signée avec identités d'asset, tenant et Incident/Run ; jointure Core tenant-scoped ; observabilité Grafana réelle et retrieval ACL filtré. NIM/Ollama seulement après contrat et grounding.
