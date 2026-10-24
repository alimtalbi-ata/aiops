# AIOps NOC — Drill-down interactif par équipement et RAG simulé

**Statut : implémentation HTML autonome en données synthétiques, non connectée à la stack réelle.**

Le module `demo/noc_drilldown.py` relie le snapshot NOC, les dépendances SAN/stockage/VMware/Payments et les six fiches du catalogue RAG. Il vérifie que les identifiants d'alerte, les équipements et les services correspondent exactement aux fiches RAG, et refuse toute divergence. Le modèle ajoute pour chaque équipement ses dépendances amont/aval, ses signaux et les étapes de diagnostic associées.

`demo/noc_wallboard.py` affiche désormais une section **Diagnostic par équipement et procédures RAG** avec panneaux dépliables HTML `details/summary` par asset. Le contenu des journaux et runbooks est échappé HTML. Une simple exécution `python -m demo.noc_wallboard --output /tmp/aiops-noc-drilldown.html` génère le dashboard complet et refuse d'écraser une sortie existante.

Tous les événements et runbooks restent **SYNTHETIC** ; les dépendances ne sont pas attestées par la CMDB, aucune commande n'est exécutée, aucun remède LIVE n'est autorisé. La section ne contient ni API métier ni secrets. `tests/test_noc_drilldown.py` et les nouveaux tests du wallboard couvrent l'association à Brocade, les dépendances, les omissions, les incohérences d'asset et l'affichage. GitHub Actions `aiops-rag-ops-fixtures.yml` a été mis à jour ; contrôler la CI du SHA le plus récent avant de déclarer qualification.

La prochaine priorité reste la liaison à Checkmk/Thruk historiques et à la timeline STAR dans un environnement isolé, puis à terme le portail :17777 après qualification des événements réellement observés.
