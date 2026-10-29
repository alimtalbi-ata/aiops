# AIOps 2.0 — Core RC1.3: installation isolée, qualification et intégrité

**Auteur : Abdelhalim Talbi**  
**Référence :** branche `feat/core-analysis-quality-v2`, PR #21  
**Version candidate :** `2.1.0-core-rc1.3`

## Objectif

Cette version de reconstruction sécurise le passage des sources au système exécutable en réduisant les interventions manuelles et en vérifiant que le nouveau déploiement ne modifie pas les anciennes stacks AIOps.

La qualification CI s'effectue dans un environnement **synthétique et isolé**. Elle n'établit ni la qualité d'un véritable modèle LLM, ni l'aptitude à exécuter des remédiations LIVE. L'activation de tels effets est bloquée par politique déterministe.

## 1. Installation et contrôle avant Docker

Depuis le kit extrait, sur un nouvel emplacement de travail (par exemple sous `/home/aiops/`) :

```bash
bash deploy/install-isolated.sh --configure-only
python3 deploy/plan_isolation.py --env .env --expected-stack aiops2-rebuild
bash deploy/install-isolated.sh
```

La première commande produit les paramètres isolés et génère les secrets privés ; elle ne lance aucun conteneur. La seconde vérifie l'identité du projet, l'adresse de liaison, les six ports et l'absence de collisions de configuration. La dernière effectue les contrôles, la compilation des images, le démarrage, les migrations, les contrôles de santé et les scénarios synthétiques.

Les identifiants de stack sont nommés ; les réseaux et volumes portent le même préfixe. L'installation refuse le nom de projet de production `aiops2`. Les interfaces ne sont exposées que sur `127.0.0.1`. Les anciennes instances et leurs volumes ne sont pas supprimés ni redémarrés.

Un contrôle supplémentaire compare le modèle Docker Compose effectivement résolu aux valeurs attendues. Les conteneurs étrangers, les volumes ou réseaux externes, les ports publics, la publication d'un port inattendu et les services privilégiés empêchent l'installation.

## 2. Diagnostiquer sans copier des journaux sensibles

```bash
python3 deploy/status.py --env .env --report reports/stack-status.json
bash deploy/diagnose.sh
```

`status.py` interroge uniquement le projet configuré. Il conserve une liste restreinte de statuts, l'état de santé et les erreurs de contrôle, sans exposer les commandes Docker, les variables d'environnement, les en-têtes HTTP, les mots de passe ni les journaux des conteneurs.

Le diagnostic `diagnose.sh` produit une collecte privée et expurgée. **Ne jamais publier cette collecte, une sauvegarde ou un fichier `.env` sans revue de confidentialité.**

`status.py` signale `UNKNOWN` plutôt que `PASS` lorsqu'un composant ne dispose pas d'un healthcheck qualifié.

## 3. Tests de défaillance du moteur Analyst/Critic

La CI rejette désormais explicitement :
- une preuve inconnue ou une identité dupliquée ;
- une métadonnée de fraîcheur injectée par le client ;
- une sévérité critique fondée uniquement sur une preuve périmée ;
- une critique validant une preuve fictive ou un état contradictoire ;
- un appel non authentifié ;
- toute prétention à l'exécution LIVE issue du modèle.

Les instructions insérées dans les logs restent des **données non fiables**. L'Analyst produit des hypothèses référencées ; le Critic les remet en question ; le Policy Gate demeure seul responsable de la disposition autorisée.

## 4. Deux niveaux distincts de qualification

**Qualification CI intégration :** fournisseur d'inférence déterministe, données synthétiques, workflows Temporal, migrations et APIs. Les résultats ne valent que pour le commit, les fixtures et les contrats testés.

**Qualification modèle réel :** configurer les variables `LLM_BASE_URL`, `LLM_MODEL` et, si nécessaire, `LLM_API_KEY` dans le fichier `.env` local, puis exécuter :

```bash
bash deploy/qualify-model.sh
```

Les métriques et les échecs sont consignés dans `reports/ai-core-evaluation.json` et le registre de qualification lorsque le Core est joignable. Aucun outil d'exécution de remédiation n'est accessible depuis l'évaluateur.

## 5. ZIP cumulatif auto-vérifiable et reproductible

La release CI produit :
- `AIOps-<version>-Core-Deployment-Kit-<horodatage>.zip` ;
- l'empreinte SHA-256 du ZIP ;
- `FILES-SHA256SUMS` avec les empreintes des fichiers internes ;
- les rapports de qualification synthétique intégrés sous `09-Qualification/`.

Après extraction des artefacts côte à côte :

```bash
sha256sum -c AIOps-*.zip.sha256
python3 tests/verify-package.py AIOps-*.zip
```

L'outil `tests/verify-package.py` valide les chemins, les entrées ZIP, les hash internes et la présence des rapports exigés avant d'accepter le kit. Il n'autorise pas le déploiement LIVE.

Le kit peut lui-même être reconditionné **sans dépôt `.git`**, au moyen de `deploy/package_tree.py` qui copie uniquement les sources, scripts, configurations de référence et documents explicitement autorisés. Cette méthode exclut les secrets, sauvegardes, caches, bases de données et liens symboliques.

## 6. Guide minimal Windows → Debian (lors de la phase de recette)

Depuis PowerShell, dans `Downloads`, transférer uniquement le ZIP qui a passé la CI :

```powershell
scp ".\AIOps-2.1.0-core-rc1.3-Core-Deployment-Kit-<horodatage>.zip" aiops@10.79.94.202:/home/aiops/
```

Remplacer `<horodatage>` par le nom réel de l'artefact. L'archive est installée dans un nouveau dossier sous `/home/aiops/`, jamais par-dessus un ancien dossier de production.

**Aucune commande d'installation, de restauration de base ou de suppression Docker ne doit être lancée tant que la qualification CI et l'intégrité du kit courant ne sont pas confirmées.**

## 7. Prochaine étape d'ingénierie

La qualification d'inférence sur le serveur de modèles réel devra documenter ses résultats bruts, son débit, ses délais, ses abstentions, la calibration et la couverture des preuves. Ensuite : intégration CMDB/RAG en lecture seule, analyse causale multi-signaux, HITL à preuve d'approbation, puis seulement extension du jumeau numérique ACME et vidéo de démonstration.

Les résultats `PASS` doivent toujours être accompagnés du commit GitHub et du rapport de CI correspondant ; les phases non exécutées restent `NOT RUN`.
