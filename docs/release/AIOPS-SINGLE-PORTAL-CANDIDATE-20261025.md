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

## Vérification indépendante du ZIP candidat (25 octobre 2026)

Le module `deploy/verify_single_portal_candidate_kit.py` est exécuté hors ligne **avant publication** du ZIP dans la CI. Il refuse les entrées ZIP dupliquées, chemins dangereux, liens symboliques, archives chiffrées, tailles excessives, sommes SHA-256 incohérentes, sources embarquées divergentes, motifs de secrets, revendications de qualification production et routes déclarées montées ou authentifiées sans preuve. Les routes sont comparées au registre Python embarqué.

Avec `--checkout .`, il exige un checkout Git propre au commit exact du manifeste et recalcule les SHA-256 de **toutes** les sources éligibles, même non embarquées. Sans `--checkout`, il n'atteste que l'intégrité interne du ZIP ; la provenance des sources absentes reste non vérifiée. Aucun mode n'atteste les routes runtime, l'authentification, les captures ou la qualification production.

```bash
python -m unittest discover -s tests -p 'test_verify_single_portal_candidate_kit.py' -v
python -m deploy.verify_single_portal_candidate_kit \
  --archive /tmp/AIOps-Single-Portal-CANDIDATE.zip --checkout .
```

**Rollback :** aucun accès Debian, réseau, conteneur ni base. Si le vérificateur refuse le kit, supprimer uniquement le ZIP candidat local, corriger sur la branche de PR, relancer les tests et ne pas forcer sa publication. Les 20 familles de composants restent `UNKNOWN` et non attestées sous :17777. La bascule nécessite une qualification E2E du runtime réel et une approbation humaine explicite.

Le ZIP candidat embarque maintenant le générateur et le vérificateur dans `sources/deploy/`. Après extraction **hors production**, la vérification interne peut être relancée avec `PYTHONPATH=sources python -m deploy.verify_single_portal_candidate_kit --archive <zip>` ; ce mode sans `--checkout` ne valide pas les références aux sources non embarquées. La CI utilise obligatoirement `--checkout .` pour vérifier leur provenance.

## Protection du contrat de non-déploiement (25 octobre 2026)

Le vérificateur refuse maintenant **toute altération**, même accompagnée d'un nouveau `metadata/SHA256SUMS`, du texte `metadata/README.md` du kit. Le générateur et le vérificateur partagent `candidate_readme()` : le contenu est comparé octet par octet avant d'accepter l'archive. Cela empêche qu'une modification du README transforme silencieusement le kit **CANDIDATE ONLY** en fausse instruction de bascule. Deux tests synthétiques couvrent la substitution de `Deployment: BLOCKED` et l'ajout d'instructions de production, chacun avec checksums recalculés. La validation de provenance `--checkout` reste indispensable pour les sources non embarquées ; la comparaison du README ne prouve ni les routes runtime, ni l'authentification, ni l'E2E. Rollback : restaurer la version antérieure de ces quatre fichiers sur la branche PR, régénérer le ZIP et requalifier hors ligne ; aucune action Debian.

## Contrôle fail-closed des routes planifiées (25 octobre 2026)

Le générateur rejette maintenant un registre où deux composants distincts partagent le même chemin. Les identifiants sont limités aux slugs ASCII minuscules ; les routes sont des chemins absolus composés de segments ASCII minuscules (lettres, chiffres, tirets), sans segments vides, `..`, `.`, pourcentage encodé, query string, fragment ou slash terminal. Le libellé doit être imprimable et non vide ; la catégorie doit appartenir aux cinq catégories du registre. **Ces validations portent uniquement sur la configuration déclarative embarquée**, et n'attestent aucune route montée ou authentifiée dans Debian.

**Motif métier :** empêcher que des routes ambiguës ou réinterprétables par un reverse proxy soient distribuées comme plan d'intégration fiable pour l'entrée unique `:17777`. Les tests synthétiques `test_reject_duplicate_planned_path_with_distinct_component_ids` et `test_reject_unsafe_route_aliases_and_invalid_registry_metadata` vérifient le refus des collisions et alias dangereux. Les routes historiques réellement configurées ne sont pas modifiées ; aucune connexion réseau n'est effectuée.

**Rollback :** revenir au commit précédent sur la branche PR uniquement, reconstruire le kit candidat et relancer la CI isolée. Le kit est non déployable ; aucune modification du runtime ni de V1/containerd n'est autorisée. Toute évolution légitime du format de route devra être revue avec le contrat de proxy avant d'assouplir ce contrôle.

## Fraîcheur obligatoire du read model NOC (25 octobre 2026)

Le code `demo/noc_portal_integration.py` refuse maintenant un snapshot `RUNTIME_READMODEL` de plus de **300 secondes** (configurable de 1 à 3600 secondes), ou daté dans le futur. La route existante `/api/noc/state` retourne HTTP 503 si son fournisseur ne peut pas prouver une observation assez récente ; `/noc` hérite du même refus. Le paramètre de test `now_utc` est une horloge synthétique injectée, jamais une preuve d'authentification. Le champ `runtime_authenticated=true` reste une **déclaration du fournisseur**, non une attestation cryptographique ; la confiance dans ce fournisseur et l'authentification du portail hôte doivent être validées séparément. Les replays historiques ne doivent pas être présentés comme l'état LIVE du NOC.

La CI du kit exécute désormais `tests/test_noc_portal_integration.py` et embarque ce fichier parmi les sources revues. Les tests couvrent une observation récente, la borne exacte de 300 secondes, une observation périmée, une date future, une horloge injectée invalide et une politique de fraîcheur invalide. Aucun accès réseau, écriture applicative, listener ou conteneur n'est impliqué.

**Rollback hors ligne :** restaurer les versions précédentes de `demo/noc_portal_integration.py`, du test, du générateur, du workflow et de cette note sur la branche PR, puis reconstruire le ZIP candidat et requalifier. Aucune modification de production n'est autorisée ; toutes les routes planifiées restent non attestées sous :17777.


## Projection publique minimale du NOC (25 octobre 2026)

Le fournisseur du read model peut contenir des champs internes (en-têtes d'authentification, notes d'exploitation, métadonnées de diagnostic). Le contrat de `/api/noc/state` **ne doit jamais sérialiser le dictionnaire brut** du fournisseur. Le module `demo/noc_portal_integration.py` applique maintenant `public_noc_snapshot()` après validation de fraîcheur, de provenance déclarée et de l'interdiction de remédiation LIVE. La projection autorise uniquement `schema`, `provenance`, `runtime_authenticated`, `live_remediation_authorized`, `run_id`, `incident_id`, `observed_at` et les couples `steps[].name/state`. Les champs inconnus, même imbriqués dans les étapes, sont exclus sans modifier l'objet fournisseur. Une erreur du fournisseur renvoie un HTTP 503 générique sans texte d'exception.

**Contexte métier :** empêcher une fuite de secrets ou de données privées depuis une source d'observation qui aurait été enrichie après sa qualification. **Interfaces :** routes déclarées `/api/noc/state` et `/noc`, dans le routeur existant non attesté monté sur Debian. **Dépendances :** Python standard pour la validation ; FastAPI uniquement lors du montage futur dans le portail existant. **Tests :** trois régressions synthétiques ajoutées à `tests/test_noc_portal_integration.py`, intégrées au workflow du kit. Le test HTTP E2E et l'authentification du fournisseur restent à qualifier ; un booléen `runtime_authenticated` n'est pas une preuve cryptographique.

**Provenance :** correction du code courant de la PR #36, pas import d'un fragment historique. Le registre `docs/recovery/` et `recovery/legacy_v2134` restent les sources de référence pour toute récupération ultérieure ; aucun ZIP historique ni secret n'est ajouté. **Rollback :** restaurer sur la branche PR la version précédente du module, du test et de cette note, puis relancer la CI hors ligne et régénérer le kit. Ne rien déployer sur Debian ; aucune action V1/containerd ou LIVE n'est permise.


## Liaison optionnelle des observations de composants NOC (25 octobre 2026)

**Besoin métier :** le point d'accès `/api/platform/components` renvoyait systématiquement les 20 familles en `UNKNOWN`, même lorsqu'un portail hôte pouvait fournir des observations de santé récentes. La nouvelle signature `create_noc_router(read_model, component_observations=None)` accepte **sans aucun appel réseau propre au module** une fonction de lecture fournie par l'application ASGI existante. Cette fonction doit retourner le dictionnaire d'observations déjà prévu par `demo/noc_platform_registry.py` : identifiant connu → `{state, observed_at, authenticated}`. Les observations authentifiées et fraîches (300 s par défaut) alimentent uniquement le champ de santé `state` ; une observation périmée ou non authentifiée demeure `UNKNOWN`.

**Frontière de confiance :** `authenticated=true` est une déclaration du fournisseur, **pas** une preuve cryptographique. Aucun composant n'est déclaré `available_in_portal=true`, aucune route n'est attestée montée et aucun état n'est promu en preuve de fonctionnement E2E. Sans fournisseur, tous les composants restent `UNKNOWN` comme auparavant. Si un fournisseur configuré lève une exception, retourne `None`, une structure invalide ou un identifiant inattendu, l'API répond **HTTP 503 générique**, sans divulguer le message du fournisseur. L'application hôte doit garantir son authentification et autoriser seulement une source de lecture fiable ; cette intégration n'est **pas** attestée dans le runtime Debian.

**Architecture/interfaces :** extension compatible du routeur FastAPI existant `demo/noc_portal_integration.py` ; aucune nouvelle route, aucun port, aucune connexion aux API GLPI/n8n/Grafana/DB/CMDB, aucun appel à Temporal, aucun accès à V1/containerd. Les 20 chemins déclarés dans le kit restent `route_mounted=false` jusqu'à une qualification séparée du routeur réel. Ce changement exploite le registre courant au lieu de recréer un moteur de supervision historique.

**Tests isolés :** `tests/test_noc_portal_integration.py` couvre désormais l'absence de fournisseur, la fraîcheur, le refus d'affirmation de route montée, les fournisseurs invalides et la réponse HTTP 503 avec masquage des exceptions. Le test HTTP utilise un faux routeur FastAPI, sans listener ni réseau ; la CI du kit exécute déjà ce fichier. La qualification d'authentification de bout en bout et la capture réelle des applications restent **NON EFFECTUÉES**.

**Provenance et déduplication :** adaptation du code courant de la PR #36, et non restauration d'un fragment de log. Les sources V2.13.4 déjà conservées sous `recovery/legacy_v2134` et le registre `docs/recovery/HISTORICAL-CODE-REGISTRY-20261023.md` restent en quarantaine documentaire jusqu'à vérification des originaux complets et SHA-256. Aucune archive, session ou capture privée n'est publiée.

**Rollback :** rétablir uniquement les versions précédentes de `demo/noc_portal_integration.py`, `tests/test_noc_portal_integration.py` et cette note sur la branche de PR ; relancer les tests isolés et reconstruire le kit candidat. Aucun déploiement ni changement de production n'a été autorisé. La bascule reste bloquée jusqu'à la qualification E2E réelle et approbation humaine.


## Corrélation explicite ticket / preuve NOC (25 octobre 2026)

**Besoin :** la timeline NOC exposait run_id et incident_id, mais ne distinguait pas l'absence d'un ticket GLPI et l'absence d'une preuve de capture. Le read model peut désormais fournir **optionnellement** ticket_id (identifiant ASCII borné) et evidence_sha256 (64 caractères hexadécimaux minuscules). Ces champs sont validés avant toute projection publique. Une valeur malformée ou une revendication evidence_runtime_attested=true entraîne un refus fail-closed (HTTP 503 via le routeur).

**Provenance et confiance :** un SHA-256 déclaré ne démontre pas que Chromium a capturé l'écran exact au bon checkpoint. L'API publie evidence_status=UNVERIFIED_DIGEST lorsqu'un digest existe, ABSENT sinon, et **toujours** evidence_runtime_attested=false. Les absences sont explicites (null), jamais remplacées par des identifiants fictifs. L'HTML NOC affiche ticket et empreinte avec échappement HTML ; il ne charge aucun service ni image externe. Aucun état de route montée n'est déduit.

**Architecture :** adaptation du contrat existant demo/noc_portal_integration.py, sans route ni port supplémentaire. Le fournisseur du portail devra ultérieurement relier ces valeurs à la chaîne authentifiée run_id / incident_id / ticket_id / checkpoint / capture / SHA et au moteur de replay déterministe. La présente modification **ne réalise pas** cette attestation ni le branchement dans Debian.

**Qualification :** trois tests isolés supplémentaires couvrent la présence d'un ticket et d'une empreinte non attestée, leur absence et le rejet de valeurs ou revendications non conformes. La CI du kit candidat exécute ce fichier ; une réussite CI ne remplace pas l'E2E réel. Aucune source historique fragmentaire n'a été promue en module complet.

**Rollback :** restaurer uniquement les versions précédentes du module, des tests et de cette documentation dans la branche de PR ; reconstruire le ZIP candidat depuis le commit épinglé et exécuter ses vérifications hors ligne. Aucune modification du runtime Debian, de V1/containerd, de GLPI/n8n/Grafana/DB/CMDB ni de la production n'est permise.

## Vue de convergence NOC sans promotion abusive de routes (25 octobre 2026)

**Besoin métier :** la route déclarée `/noc` présentait uniquement l'incident ; l'opérateur ne pouvait pas consulter les 20 familles et distinguer une observation de santé d'une route réellement intégrée. Le rendu `render_noc_dashboard()` affiche désormais la chronologie et un tableau des **20 composants**, leurs chemins planifiés et leur état de santé fourni par le registre existant. **Aucun lien vers un backend privé n'est activé** : les chemins sont du texte, chaque route est explicitement `NON ATTESTÉE`. Le composant refuse un inventaire qui revendique `available_in_portal=true`, une route différente du registre ou une identité contradictoire. Les valeurs incident et chronologie sont échappées HTML ; aucun JavaScript ni accès réseau n'est ajouté.

**Interfaces et limites :** réutilisation de `/noc`, `/api/noc/state` et `/api/platform/components` via le routeur FastAPI **déclaré dans le code**, non attesté monté sur Debian :17777. La santé observée et `runtime_authenticated=true` sont des déclarations du fournisseur, pas des preuves cryptographiques. Si le fournisseur d'inventaire est invalide, la page renvoie HTTP 503 générique. Aucune route supplémentaire, aucun port, proxy, conteneur ou backend n'est modifié. La navigation effective vers GLPI/n8n/Grafana/Temporal exige une intégration et une attestation distinctes.

**Provenance et déduplication :** adaptation du module courant `demo/noc_portal_integration.py` et du registre existant `demo/noc_platform_registry.py`, sans réimporter d'archive historique incomplète. Les références F20.13 et Hybrid Replay V2.13.4 restent inventoriées dans `docs/recovery/` et `recovery/legacy_v2134` sans être présentées comme sources complètes qualifiées.

**Tests isolés :** trois régressions dans `tests/test_noc_portal_integration.py` : 20 lignes et absence de liens non attestés, échappement HTML d'une étape hostile, refus d'une route prétendument montée ou détournée. Ces tests ne démontrent pas un montage sur le runtime réel ni la cinématique ACME P1 → Payments P2.

**Rollback :** restaurer sur la branche PR le module, ses tests et cette documentation depuis le commit parent, régénérer et vérifier le ZIP candidat, puis relancer les workflows isolés. Aucun déploiement Debian ou modification LIVE autorisé.


## Raccordement fail-closed de l'identité n8n 02→03 au NOC (25 octobre 2026)

**Fonction métier :** le read model NOC peut maintenant recevoir un `correlation_id` et, optionnellement, les observations exactes `handoff_02_03` des quatre étapes `webhook_02`, `rag_02`, `canonical_02` et `prepare_analyst_03`. Le contrôle réutilise **sans réécriture** `demo/star_n8n_identity_gate.py:verify_handoff`, déjà présent sur la branche PR. Une étape manquante, une identité divergente, un champ alias, une corrélation absente ou un désaccord avec `run_id`/`incident_id` du NOC provoque un refus (HTTP 503 générique via le routeur). Aucune identité manquante n'est inventée.

**Projection publique :** seuls `correlation_id`, `handoff_status` (ABSENT ou CONSISTENT_UNAUTHENTICATED), `handoff_identity_sha256` et `handoff_runtime_authenticated=false` sont ajoutés ; les quatre objets bruts ne sont jamais publiés. L'écran `/noc` affiche la cohérence **non authentifiée** et son empreinte, jamais une réussite d'exécution n8n, une approbation HITL ou une preuve d'impact Payments P2. Toute revendication `handoff_runtime_authenticated=true` est rejetée. Le contrôle prouve seulement la cohérence des observations fournies, pas leur origine réelle.

**Intégration et provenance :** contrat Python pur entre `demo/noc_portal_integration.py` et le gate existant ; aucune nouvelle route, API réseau, écriture GLPI/n8n/DB, port, conteneur ni connexion Debian. Les deux sources et leurs tests sont désormais inclus dans le sous-ensemble du ZIP candidat, les autres sources restent référencées par commit Git et SHA-256. Il s'agit d'une réutilisation de code actuel, **pas** de la promotion d'un fragment historique. Les originaux F20.13 et Hybrid Replay restent en quarantaine jusqu'à qualification complète.

**Tests/rollback :** les tests synthétiques vérifient absence explicite, identité cohérente, divergence, étape manquante, alias frauduleux, incohérence avec le NOC, projection sans fuite et attestation forgée. La CI du kit exécute aussi la suite existante `test_star_n8n_identity_gate.py`. Pour annuler, restaurer uniquement ces cinq fichiers depuis le commit parent sur la branche de PR, reconstruire et vérifier le ZIP hors ligne ; **aucune intervention sur :17777**. Montage du routeur et E2E réel restent NON ATTESTÉS ; production NON AUTORISÉE.


## Mise à jour PR #36 — route STAR publique et récupération historique (25 octobre)

Le portail candidat enregistre désormais, dans `app/portal/main.py`, le routeur
public strictement synthétique `portal_demo_public_v21310.router` sur la même
application FastAPI : `GET /demo/` et `GET /demo/star`. Le scénario ne lance pas
de processus ni d'appel aux API métier ; l'asset HTML local est inclus dans la
liste d'embarquement explicite du kit cumulatif. La CI vérifie que la route est
présente après import isolé du portail, que l'asset reste autonome, et que le ZIP
embarque les octets exacts et leur SHA-256 dans le manifeste. Ces contrôles sont
source-level/offline, non une attestation de la route sur Debian.

Le registre NOC reste indépendant et **non monté**, faute de read model issu du
pipeline réel et de mécanisme d'authentification/provenance runtime qualifié. Les
20 routes de composants restent `UNKNOWN`, `route_mounted=false` et
`runtime_authenticated=false`.

La récupération historique ne remplace pas les originaux : le registre existant
`docs/recovery/OCTOBER-2026-CUMULATIVE-ZIP-OPAQUE-NESTED-V21363.md` consigne
l'archive originale `AIOPS-V21310-STAR-PORTAL.zip` (SHA-256
`cdca139131dbbac7adb2f811077c25e94dd01899a6ec33c37ea067d26a351d87`) et le
SHA-256 de son membre historique `portal_demo_public_v21310.py`
(`5bee897914ec958af0f715f24eee229b9f9539a3df5da4f9c43cb8746ad60ee0`).
La version actuelle du fichier dans cette PR est un objet Git distinct :
`128b3fae541e070d29ab8cb78e3e8bfbd5880d0b` (Git blob SHA, pas SHA-256 du fichier).
La branche utilise la version actuelle revue, sans écraser ni republier l'archive
historique. Le générateur continue de calculer les sommes SHA-256 des octets
courants embarqués ; les archives privées, sessions et captures historiques ne
sont pas ajoutées au kit.

**Rollback :** revert des changements source, test, workflow et documentation de
la PR ; aucun rollback runtime, DB, conteneur ou port n'est requis. Production
reste NO-GO en attendant l'E2E authentifié du runtime et l'approbation explicite.
