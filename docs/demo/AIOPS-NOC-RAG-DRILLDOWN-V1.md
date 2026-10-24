# AIOps NOC — Drill-down interactif par équipement et RAG simulé

**Statut : implémentation HTML autonome en données synthétiques, non connectée à la stack réelle.**

Le module `demo/noc_drilldown.py` relie le snapshot NOC, les dépendances SAN/stockage/VMware/Payments et les six fiches du catalogue RAG. Il vérifie que les identifiants d'alerte, les équipements et les services correspondent exactement aux fiches RAG, et refuse toute divergence. Le modèle ajoute pour chaque équipement ses dépendances amont/aval, ses signaux et les étapes de diagnostic associées.

`demo/noc_wallboard.py` affiche désormais une section **Diagnostic par équipement et procédures RAG** avec panneaux dépliables HTML `details/summary` par asset. Le contenu des journaux et runbooks est échappé HTML. Une simple exécution `python -m demo.noc_wallboard --output /tmp/aiops-noc-drilldown.html` génère le dashboard complet et refuse d'écraser une sortie existante.

Tous les événements et runbooks restent **SYNTHETIC** ; les dépendances ne sont pas attestées par la CMDB, aucune commande n'est exécutée, aucun remède LIVE n'est autorisé. La section ne contient ni API métier ni secrets. `tests/test_noc_drilldown.py` et les nouveaux tests du wallboard couvrent l'association à Brocade, les dépendances, les omissions, les incohérences d'asset et l'affichage. GitHub Actions `aiops-rag-ops-fixtures.yml` a été mis à jour ; contrôler la CI du SHA le plus récent avant de déclarer qualification.

La prochaine priorité reste la liaison à Checkmk/Thruk historiques et à la timeline STAR dans un environnement isolé, puis à terme le portail :17777 après qualification des événements réellement observés.

## 24 octobre 2026 — cohérence des assets et échec CI reproduit

Le workflow `AIOps simulated NOC RAG corpus qualification` (run
`40135171153`) a signalé un échec vérifié de
`test_mismatched_corpus_rejected` : une alerte conservait un `event_id`
présent dans le catalogue RAG mais son `asset_id` avait été remplacé
par `not-original`. L'ancienne boucle du drill-down ne parcourait que
les équipements connus de la topologie et **ignorait silencieusement**
cette alerte orpheline ; le wallboard pouvait donc afficher un diagnostic
incomplet comme si le jeu d'alertes était cohérent.

Le correctif de `demo/noc_drilldown.py` vérifie maintenant, avant de
construire les panneaux, que chaque `asset_id` d'alerte appartient aux
nœuds de la topologie synthétique. Un asset inconnu produit `ValueError`
et empêche la génération du HTML. Le test de régression
`test_orphan_alert_asset_is_rejected_not_silently_dropped` complète le
test existant du wallboard. Il s'agit d'un contrôle **fonctionnel** de
l'exhaustivité des alertes, pas d'une attestation de la CMDB.

**Qualification :** le run cité établit l'échec antérieur. La réussite
du SHA corrigé doit être vérifiée séparément dans GitHub Actions ;
ne pas confondre publication du correctif et CI verte.

**Rollback :** revenir uniquement sur le changement ciblé du
drill-down et son test, dans la branche de PR après revue. Ce rollback
réintroduirait le défaut de disparition silencieuse des alertes et n'est
pas recommandé. Aucun changement de runtime Debian, conteneur,
port, base, GLPI, n8n, Grafana ou CMDB n'est nécessaire.
