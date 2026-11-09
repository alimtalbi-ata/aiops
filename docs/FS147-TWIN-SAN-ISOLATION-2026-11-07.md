# FS147 — exclusion Twin SAN et contrat de non-contamination (2026-11-07)

Référence : [FS.364](FS364-ARCHITECTURE-REPRISE-2026-11-06.md). Qualification **source-only**, sans preuve d'exécution sur Debian.

## Décision et frontière

L'incident GLPI **147** (`AIOPS2-REAL-FS-20261106`) concerne le montage tmpfs `/fs-lab` du conteneur `aiops2-fs-lab`. FS.364 rapporte une mesure ponctuelle de **92 %** le 2026-11-06 et précise que Core ne monte pas ce chemin. Aucune dépendance de ce diagnostic filesystem vers la fabric `ACME-SAN-FABRIC-A` n'est établie. **Twin SAN non requis** pour l'inspection en lecture seule; son invocation ne doit pas être déduite d'un simple mot « SAN » dans une source légitime telle que `filesystem-sanity-check`.

La séparation exigée porte sur : graphe (`filesystem-lab` vs `twin-san`), namespace (`fs-lab` vs `acme-san`), incident, RUN, Evidence, observations (`/fs-lab` et `aiops2_fs_lab_used_percent` vs fabric SAN) et arêtes de dépendance. Aucune arête inter-graphe, aucun alias Twin imbriqué, aucune Evidence SAN réutilisée comme preuve FS147. Les identifiants RUN/Evidence dans le test sont **explicitement fictifs**; ne pas les confondre avec un RUN réellement lié à GLPI 147.

## Contrat E2E négatif livré

`tests/test_fs147_twin_san_isolation_contract.py` vérifie en mémoire un cas isolé positif et les rejets suivants : arête vers Evidence SAN, clé imbriquée Twin, remplacement d'ID ou de namespace, référence filesystem dans une observation SAN, absence de mesure, substitution de provenance source/métrique filesystem et rejeu de métrique filesystem dans SAN. Il autorise `filesystem-sanity-check`. Ce test ne prouve **ni l'absence de fuite dans le système vivant, ni un RUN 147 existant** : il fixe un invariant à réutiliser lors du branchement de snapshots read-only réels, avec provenance et horodatage.

Commande sans dépendances supplémentaires : `python3 -m unittest discover -s tests -p 'test_fs147_twin_san_isolation_contract.py' -v`.

Pour l'E2E réel : obtenir depuis les API autorisées un même `alert_fingerprint -> incident_id -> run_id -> evidence_id -> glpi_ticket_id=147`, les événements Worker/Temporal/Portal, les observations read-only `df/du/ls` prises dans le lab, et les relations de dépendance. Appliquer les mêmes invariants aux deux graphes. Refuser les données DEMO comme preuve LIVE, les RUN historiques BLOCKED, les validations de GLPI 146 et toute corrélation partielle. Préserver STOP_AUTO, Policy, HITL.

## Qualification et partage inter-rôles

- **Twin** : propriétaire de l'invariant d'absence de contamination et de l'exclusion documentée.
- **Core** : fournir IDs, provenance, idempotence et liaison native à 147, sans ticket doublon.
- **Worker** : fournir mesures lab et Evidence horodatées, sans prétendre que Core monte `/fs-lab`.
- **Portal** : afficher statut BLOCKED/UNKNOWN et preuve de RUN, sans convertir une fixture en succès.
- **Intégration** : assembler la chaîne E2E et les gates CODE / CI / HÔTE / EXÉCUTÉ.

Docker rootless FS1106/FS1107 : **si** un futur test nécessite un conteneur publié, le créer sur `aiops2-rebuild-public` avec `--publish` explicite, puis seulement connecter `aiops2-rebuild-control`, `aiops2-rebuild-integration`, `aiops2-rebuild-observability`, en revérifiant HTTP et PortBinding à chaque étape. Ce test Python ne crée aucun conteneur et ne modifie aucun réseau.

FS1113 / candidat fs1097 : hors périmètre de ce test ; ne pas reconstruire, démarrer ni déployer le Portal production `aiops2-portal:fs1073-csp-candidate`. Les gates Chromium/CSP/history restent indépendants et doivent être qualifiés avant toute promotion.

**Gates à l'ouverture de PR** : CODE = commit publié ; CI = non attestée au SHA ; HÔTE = non vérifié ; EXÉCUTÉ = fixture non exécutée ici / E2E réel non démontré. Pas de merge, déploiement, suppression, truncate, approbation simulée ou remédiation.

## Qualification complémentaire — 2026-11-07

Le commit `e1e75c9` renforce le contrôle de provenance des observations : un montage `/fs-lab` seul ne suffit plus si `source` ou `metric` ont été substitués, et le SAN ne peut pas réutiliser `aiops2_fs_lab_used_percent`. Deux régressions négatives supplémentaires sont ajoutées. Ce contrat reste fondé sur fixtures : il ne prétend pas qualifier des données réelles ni une signature cryptographique de provenance.

Au SHA précédent `6570300d35e73ecc80511b530b9fbba52975236f`, GitHub Actions retourne trois workflows réussis (Offline Integrity, Historical Trace, Core isolated) et `AIOps quality gates` en échec. Ne pas reporter ces résultats comme CI du nouveau HEAD. La suite dédiée et les snapshots hôte/E2E restent à qualifier au SHA exact ; PR Draft et NO-GO maintenus.

## Contrôle supplémentaire — métrique filesystem imbriquée dans SAN

Commit `836bdaf` : `test_reject_nested_filesystem_metric_in_san` couvre le rejeu de `aiops2_fs_lab_used_percent` dans `observations[].metadata.metric` du graphe SAN. Le validateur inspecte désormais récursivement les clés et valeurs des observations SAN, et non seulement `observations[].metric` au premier niveau. Ce cas évite qu'une métrique filesystem soit blanchie par un emballage de métadonnées. Le contrôle reste **fixture-only** ; il ne prouve pas la non-contamination d'un RUN réel. Qualification au SHA exact requise avant merge.

## Renforcement — observations additionnelles (2026-11-07)

Le test `test_reject_extra_unqualified_lab_observation` interdit de joindre à une observation `/fs-lab` légitime une seconde observation de source ou métrique non qualifiée. Le validateur exige désormais `filesystem-sanity-check`, `/fs-lab` et `aiops2_fs_lab_used_percent` **pour chaque observation lab**, et pas seulement pour au moins une. Il s'agit d'une règle stricte de fixture, à confronter au schéma des snapshots réels avant toute réutilisation E2E. Une observation inconnue ne doit pas être acceptée silencieusement.

**Limite documentaire** : le chemin de référence `docs/FS364-ARCHITECTURE-REPRISE-2026-11-06.md` n'a pas été retrouvé sur la branche de base lors de la consultation GitHub (404). La décision Twin non requis est donc *provisoire*, fondée sur les éléments rapportés ci-dessus, en attente d'une référence FS.364 vérifiable par SHA. Le RUN réel, ses Evidence et ses dépendances ne sont pas qualifiés. CI, HÔTE et EXÉCUTÉ doivent rester distincts.

## Régression supplémentaire — provenance filesystem imbriquée côté SAN

Le contrôle SAN rejette désormais `filesystem-sanity-check` même si la chaîne n'apparaît que dans `observations[].metadata.producer`, sans champ `mount` ni métrique filesystem. Le test négatif `test_reject_nested_filesystem_source_in_san` protège contre le blanchiment de provenance par métadonnées. Ce test est **source/fixture-only** : aucune absence de fuite réelle n'est revendiquée. Le gate reste NO-GO sans exécution au SHA exact, référence FS.364 accessible et snapshots read-only du RUN 147.
