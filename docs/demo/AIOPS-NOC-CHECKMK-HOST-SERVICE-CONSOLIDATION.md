# AIOps NOC — Consolidation d'états Checkmk hôtes/services

Le module `demo/noc_checkmk_consolidation.py` réunit les exports hors ligne précédemment normalisés : `aiops-checkmk-offline-readonly-v1` pour les hôtes et `aiops-checkmk-services-loopback-v1` pour les services. Il distingue l'état de l'hôte lui-même (`host_state`) de l'état global tenant compte de ses services (`overall_state`), ce qui permet de signaler un port FC critique sur un équipement dont le check de disponibilité répond OK.

Le traitement refuse les services associés à un hôte absent, les doublons de couple hôte/service, les décalages entre fenêtres de capture, les mauvais schémas et toute revendication d'authentification runtime. Aucun état n'est deviné si une donnée manque.

**Provenance :** `UNVERIFIED_OFFLINE_EXPORTS`, `runtime_authenticated=false`, `live_remediation_authorized=false`. Il ne s'agit ni d'une connexion Checkmk de production, ni d'une attestation Thruk, ni d'un état CMDB vérifié. Les états synthétiques du démonstrateur restent un flux distinct.

Cinq tests unitaires ciblés sont ajoutés dans `tests/test_noc_checkmk_consolidation.py` et exécutés par `.github/workflows/aiops-rag-ops-fixtures.yml` : passage d'un service CRIT à l'état consolidé, service orphelin, horodatages divergents, statut LIVE falsifié et service dupliqué.

**Prochain jalon :** intégrer ce modèle à une page NOC explicitement étiquetée « export hors ligne non authentifié », puis qualifier des captures Chromium réelles de cette page. Reprendre la configuration historique Thruk/Checkmk avant toute connexion au serveur Debian `:17777`.
