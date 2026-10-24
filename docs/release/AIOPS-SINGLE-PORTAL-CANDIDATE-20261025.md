# AIOps 2.0 — Kit cumulatif de convergence portail unique (candidat, 2026-10-25)

## Périmètre et autorité

Source de vérité : dépôt `alimtalbi-ata/aiops`, PR draft #36, commit exact indiqué par `metadata/source-manifest.json`. Entrée cible **unique** : `http://10.79.94.202:17777/`. **Ce document n'autorise ni accès à Debian, ni déploiement, ni ouverture de port, ni modification de V1/containerd, GLPI, n8n, Grafana, DB/CMDB, ni remédiation LIVE.**

Le générateur `deploy/single_portal_candidate_kit.py` construit hors ligne un ZIP cumulatif de **candidature** : sources revues embarquées, inventaire SHA-256 de toutes les autres sources texte suivies par Git, référence exacte du commit, manifeste de routes prévues et sommes SHA-256 du contenu. Les sources non embarquées sont récupérables depuis ce commit Git, **pas** depuis le ZIP seul. Les chemins privés, sessions, archives historiques, captures, dumps et secrets ne sont pas embarqués. Un scanner de motifs connus est une barrière supplémentaire, **pas une garantie d'absence de secrets** : une revue de release reste obligatoire.

Exécution en CI uniquement, ou dans un checkout isolé et propre :

```bash
python -m unittest discover -s tests -p 'test_single_portal_candidate_kit.py' -v
python -m unittest discover -s tests -p 'test_noc_browser_workflow_contract.py' -v
python -m deploy.single_portal_candidate_kit --root . \
  --commit "$(git rev-parse HEAD)" --output /tmp/AIOps-Single-Portal-CANDIDATE.zip
unzip -tqq /tmp/AIOps-Single-Portal-CANDIDATE.zip
```

La CI `single-portal-candidate-kit.yml` publie le ZIP et son SHA-256 comme artefacts temporaires de PR **seulement si les tests et la génération passent**. Ne jamais publier ce kit sous une étiquette « prod-ready ».

## Routes : état constaté dans le code, pas dans le runtime

Le registre `demo/noc_platform_registry.py` contient 20 familles : NOC, Checkmk, Thruk, Grafana, Prometheus, Alertmanager, GLPI, n8n, Core, Temporal, Worker, DGX Analyst/Critic, Policy/HITL, Evidence, RAG, Digital Twin, Simulator, Copilot, Mattermost, PagerDuty. Les chemins réservés figurent dans `metadata/planned-routes.json`.

**Statut du code vérifié :** `demo/noc_portal_integration.py` définit `create_noc_router`, proposant `/noc`, `/api/noc/state` et `/api/platform/components`, mais ce routeur n'est **pas prouvé monté** dans le portail déployé. Tous les chemins du registre restent `route_mounted=false`, `state=UNKNOWN`, `runtime_authenticated=false`. Aucune route GLPI/n8n/Grafana n'est attestée fonctionnelle sous `:17777`. Le ZIP ne crée aucun listener et ne configure aucun proxy.

## Préflight en lecture seule (procédure à faire approuver, NON exécutée)

1. Identifier le processus et l'image réellement liés à `:17777`, le routeur HTTP, le middleware d'authentification, la version, les réseaux existants et les chemins de proxy. **Ne jamais** lancer de `docker compose up/down`, `restart`, `exec` mutateur ou installer depuis cette procédure.
2. Inventorier les routes existantes et tester uniquement des GET approuvés depuis un environnement d'intégration isolé ; toute absence de route/authentification/provenance devient `UNKNOWN` ou HTTP 503.
3. Vérifier sauvegardes et restauration à blanc sur une copie ; consigner SHA-256 des configurations, image précédente, mapping des routes, identité et limites.
4. Rejouer ACME SAN P1 → impact Payments P2 en **SIMULATION** sur données synthétiques, via le chemin métier qualifié ; confronter les 9 checkpoints à Core/Temporal, DGX Analyst/Critic, RAG, Policy/HITL, GLPI/n8n et Evidence.
5. Capturer Chromium uniquement en contexte isolé, avec source/identité/authentification et timestamp explicites ; l'absence de capture ou l'écran de login ne constitue pas une preuve. Bloquer toute transition 02→03 sans identité cohérente.

## Incident CI Chromium et remédiation

La CI `STAR Chromium actual offline fixture render` sur `acef8177` a échoué après les tests navigateur : le job tentait de lire `evidence-index.json` **avant** sa création. Le gate brut accepte exactement `manifest.json` et trois PNG, puis refuse les fichiers additionnels. L'ordre corrigé est donc : **rendu PNG → vérification brute → génération index → cue map → trace → centre de preuves**. Le test `test_noc_browser_workflow_contract.py` empêche de réintroduire l'inversion. L'état de réussite CI du correctif doit être confirmé sur le SHA courant ; aucune preuve E2E Debian n'en découle.

## Patrimoine historique et déduplication

Le kit ne réimporte pas les archives historiques. Le registre `docs/recovery/HISTORICAL-CODE-REGISTRY-20261023.md`, les fiches F20.13 et `recovery/legacy_v2134` restent les références de provenance/SHAs/conditions de réutilisation. Les collecteurs Playwright historiques non qualifiés et les pages de connexion ne sont jamais promus en preuves runtime. Les modules complets récupérés doivent être comparés au code existant, testés et explicitement revus avant inclusion dans une release.

## Blocages de bascule et rollback

**Bascule interdite** tant que le portail réellement déployé, l'auth/SSO, les connexions des 20 familles, le replay déterministe, les neuf captures attestées et le runtime E2E Temporal ne sont pas qualifiés, et tant qu'une approbation humaine explicite manque.

Le kit lui-même ne modifie aucun système : rollback du kit = suppression locale du ZIP candidat. Pour une future intégration approuvée, conserver et vérifier l'image/configuration/routes précédentes et les sauvegardes, prévoir un retour atomique à la version antérieure sur environnement d'intégration, puis prouver la restauration avant toute décision de production. Ne pas toucher à V1/containerd.
