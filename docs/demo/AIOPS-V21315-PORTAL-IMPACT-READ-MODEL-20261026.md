# AIOps — API/écran d'impact ACME local (26 octobre 2026)

**Statut :** nouveau read model local et déterministe, non intégré aux backends et non qualifié en production.

## Besoin métier
Offrir depuis le portail existant une vue exploitable du scénario synthétique ACME SAN P1 → Payments P2, tout en exposant honnêtement les trous de preuve. Le besoin n'est pas de fabriquer un run, un ticket GLPI, un horodatage ou une capture. Cette vue complète les routeurs statiques existants sans introduire un second portail.

## Routes et interfaces
- `GET /api/demo/acme-impact` : JSON read-only avec `run_id`, incident source et impact, chemin de dépendances, SHA-256 de la source et champs manquants explicites.
- `GET /demo/acme-impact` : écran HTML local affichant les mêmes valeurs. Il ne contient ni script, ni formulaire, ni lien, ni appel réseau externe.
- Les deux routes sont montées sur `portal.main:app`. Aucun listener, port, worker ou tâche d'arrière-plan n'est ajouté.

## Architecture et provenance
Le contrôleur lit les octets exacts de `app/portal/acme-fixtures.json`, appelle `load_fixture_bytes()` et `validate_fixture()` depuis le contrat stdlib `portal.acme_fixture_contract`, puis calcule SHA-256 sur ces mêmes octets. Le validateur historique sous `demo/integrations/v21315/validate_fixture.py` est un wrapper de compatibilité qui réutilise ce contrat commun. Un identifiant `SIM-ACME-<16 hex>` est dérivé du digest : `run_id_provenance=DERIVED_FROM_FIXTURE_SHA256_NOT_RUNTIME_RUN`. Ce n'est **pas** un identifiant Core/Temporal.

- `incident_id` = incident source synthétique SAN P1 ; `impact_incident_id` = incident cible Payments P2.
- `ticket_id=null`, provenance `ABSENT_NO_GLPI_WRITE` : aucun ticket GLPI réel n'est créé ni prétendu.
- `event_timestamp_utc=null`, provenance `ABSENT_NO_RUNTIME_EVENT` : aucun événement runtime n'est daté.
- L'écran peut aussi montrer un `simulation_ticket_id` déterministe préfixé `SIM-GLPI-` et le checkpoint fixe `2026-10-25T09:00:00Z`; leurs provenances `SYNTHETIC_LABEL_NOT_A_GLPI_TICKET` et `FIXED_SCENARIO_CLOCK_NOT_RUNTIME_EVENT` interdisent de les confondre avec GLPI ou un événement réel.
- `source_sha256` atteste l'identité des octets du fixture uniquement ; il n'atteste ni une capture, ni GLPI, ni n8n, ni Grafana, ni un runtime.
- `runtime_evidence_present=false`, `runtime_attested=false`, `production_qualified=false`, `live_remediation_authorized=false`.

## Dépendances et conditions de réutilisation
La route dépend de FastAPI et du module stdlib `portal.acme_fixture_contract`, embarqués dans le même répertoire `portal/` que l'application, plus le fichier fixture voisin. Le chemin du fixture est fixe, non fourni par la requête. Un fixture absent, symlink ou invalide produit un HTTP 503 générique, sans contenu partiel. Le contrat est importé au démarrage du module : sa présence dans l'image est donc un prérequis de packaging, vérifié par le build d'image et le smoke test CI (sans listener).

## Tests
`tests/test_portal_acme_impact_read_model.py` vérifie l'unicité/méthode des routes, le SHA-256 lié aux mêmes octets que ceux validés, la répétabilité des réponses, les champs ticket/temps absents, les limites d'attestation, le refus 503 du fixture invalide/absent, l'encodage HTML, la CSP et le rejet des méthodes mutatrices. Le test du chargeur binaire vérifie également les clés JSON dupliquées et UTF-8 invalide. CI sur données locales uniquement.

## Durcissement fail-closed (26 octobre 2026)

Le validateur contrôle désormais explicitement le type de `severity` avant toute appartenance à l'ensemble autorisé. Une valeur JSON de type liste/objet (non hashable), nombre ou `null` est rejetée par une `ValueError` contrôlée au lieu de produire un `TypeError` non géré. La route du portail transforme le fixture mal formé en HTTP 503 générique, sans détails internes ni payload partiel. Les tests unitaires couvrent cinq types invalides ; un test ASGI vérifie le refus HTTP. Cela ne change pas le contrat métier et n'introduit aucun appel runtime.

## Historique et garde-fous
Le validateur et le fixture ACME sont déjà inventoriés dans `docs/recovery/HISTORICAL-CODE-REGISTRY-20261023.md` et `docs/recovery/OCTOBER-2026-ARCHIVE-CONTEXT-AND-REUSE.md`. Aucun ZIP original, secret ou extrait tronqué n'est réimporté ou déclaré complet par ce changement.

## Inventaire d'impact détaillé (évolution de la branche)

Le contrat de validation renvoie maintenant `affected_cis` en plus de
`affected_ci_ids`. Chaque élément expose `id`, `kind`, `name`,
`depends_on` et `impact_role`. Les rôles sont calculés à partir des
identifiants du scénario : `INCIDENT_SOURCE`, `BUSINESS_SERVICE_TARGET`
ou `TRANSITIVE_DEPENDENCY`. L'ordre des CI et des dépendances est trié pour
rendre le résultat reproductible.

Le read model JSON transmet cette collection et l'écran HTML présente une
carte par CI affectée, avec son nom, son type, son rôle et ses dépendances
déclarées. Cela rend le rayon d'impact plus directement exploitable pour le
diagnostic et la présentation. Le fabric B reste hors du rayon de l'incident
sur le fabric A, mais apparaît comme dépendance redondante sur les fiches hôte
et volume : cette distinction ne prétend pas démontrer l'état réel des chemins.

Les tests ajoutés vérifient les métadonnées du volume, les dépendances de la
VM, les rôles de chaque CI, l'affichage des cartes et l'exclusion du fabric B
du rayon calculé. La qualification reste à confirmer par les workflows GitHub ;
les modifications de code et la présence des tests ne valent pas preuve de
passage CI.

## Qualification, déploiement et rollback
Ce patch ne contacte aucun service et ne change aucune donnée. Il n'a été soumis qu'à la branche de PR. La restauration/annulation consiste à revert les commits du changement puis relancer les workflows ciblés ; aucune sauvegarde de base, intervention Debian, ouverture de port ou opération sur conteneur n'est nécessaire pour ce changement. **E2E runtime et production restent non qualifiés** jusqu'à une intégration authentifiée distincte, à des tests navigateur sur les vrais écrans autorisés, à des preuves indépendantes et à une approbation humaine de bascule.

## Correctif de packaging pour le portail (26 octobre 2026)

Le Dockerfile du portail construit depuis le contexte `app/` et ne copie que
`shared/` et `portal/`. Le validateur et le fixture historiques situés sous
`demo/integrations/v21315/` ne sont donc pas des ressources disponibles dans
l'image du portail. La lecture du read model devait échouer en mode fermé dans
cette image, même si les tests exécutés depuis le checkout complet réussissaient.

Le contrat stdlib partagé est désormais installé à
`app/portal/acme_fixture_contract.py`, avec son fixture synthétique à
`app/portal/acme-fixtures.json`. Le CLI historique sous
`demo/integrations/v21315/validate_fixture.py` est conservé comme wrapper
compatible et importe le contrat commun ; les tests comparent les octets des
deux fixtures et les rapports de validation. Le read model lit uniquement les
fichiers voisins de son propre module, donc inclus par le `COPY portal` déjà
présent. Aucun contexte Docker, port, listener ou service supplémentaire n'est
nécessaire.

La CI ACME compile les modules et tests concernés, garde les validations CLI
normale et `python -O`, exécute les tests unitaires, puis construit l'image du
portail et lance seulement `python -c` dans un conteneur éphémère. Le smoke test
ne publie aucun port et ne démarre pas Uvicorn ; il vérifie l'impact déterministe
SAN P1 → Payments P2 ainsi que l'absence de ticket, d'horodatage runtime et
d'autorisation LIVE.

Cette validation demeure synthétique. Elle ne démontre ni l'authentification
des backends, ni les neuf captures applicatives STAR, ni la provenance
indépendante, ni l'intégration Debian. Les champs `runtime_attested`,
`production_qualified` et `live_remediation_authorized` restent faux.

## Lecture du fixture sans suivre de lien symbolique (26 octobre 2026, nouveau)

Le read model utilise désormais `_read_fixture_bytes_safely()` au lieu d'une
séquence pathname `is_symlink()/read_bytes()`, vulnérable à un remplacement
entre la vérification et l'ouverture. Le helper ouvre le fichier avec
`O_NOFOLLOW` et `O_CLOEXEC` lorsque disponibles ; si `O_NOFOLLOW` n'existe pas,
il échoue de façon fermée. `O_NONBLOCK` empêche un FIFO substitué d'attendre
indéfiniment avant le contrôle `fstat`.

Le descripteur ouvert doit désigner un fichier régulier, inférieur ou égal à
256 KiB. Les métadonnées du descripteur (device, inode, mode, taille, mtime et
ctime) sont comparées avant/après lecture et la taille des octets lus doit
correspondre à celle du fichier stable. Le validateur et le calcul SHA-256
consomment ensuite la même chaîne d'octets en mémoire : aucune seconde
résolution du chemin ne peut substituer un autre fichier entre validation et
hachage. Une lecture remplacée, trop grande, non régulière ou instable produit
la même erreur HTTP 503 générique.

Tests ajoutés : lien symbolique, fichier surdimensionné, FIFO sans blocage et
mutation du fichier entre `fstat` initial et final. Les tests utilisent des
fichiers temporaires synthétiques ; ils ne contactent aucun backend ni ne
modifient le fixture du dépôt. La limitation de taille constitue un contrat de
packaging local, pas un mécanisme d'authentification du producteur des données.

Le portage cible est Linux/Debian et l'image Python Linux. Les plateformes sans
`O_NOFOLLOW` échouent volontairement en mode fermé ; le fallback portable qui
suivrait les liens n'est pas activé. Le scénario, ses IDs, et sa provenance
restent synthétiques ; aucun ticket, timestamp runtime ou attestation n'est
créé.

## Navigation du portail — 27 octobre 2026

Le shell partagé `app/portal/ui_theme.py` expose maintenant deux vues déjà montées
sur la même application FastAPI : `/noc` (inventaire statique des routes, pas un
NOC connecté) et `/demo/acme-impact` (impact ACME synthétique, strictement local).
Les liens ne lancent pas de workflow, ne contactent aucun backend et n'ajoutent
aucun listener ni port.

Le kit cumulatif embarque désormais `app/portal/ui_theme.py` avec le test qui
vérifie la présence unique des deux liens dans le shell. Le plafond de membres
du vérificateur est ajusté de 64 à 68 pour accepter le nouveau fichier embarqué
sans relâcher les contrôles de liste exacte, doublons, empreintes ou statut
`production_qualified=false`.

Cette amélioration corrige la découvrabilité dans l'interface commune ; elle ne
transforme ni `/noc` ni les connecteurs projetés en intégrations runtime.
Les connexions directes à GLPI/CMDB, n8n, Grafana, Prometheus, Checkmk/Thruk,
Temporal, DGX et RAG restent à raccorder et à qualifier séparément.
