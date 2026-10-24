# AIOps STAR — cinématique et captures applicatives (22 octobre 2026)

**Statut : conception/contrat, aucune capture réelle ni parcours navigateur qualifié dans ce commit.**

## Objectif
Deux scénarios synthétiques ACME : **SAN fabric P1** (défaillance FC Brocade, multipath, impact Payments) et **Payments P2** (dégradation applicative liée ou indépendante, hypothèses alternatives et critique IA). Les identifiants doivent être stables sur toute la chaîne : run_id, incident_id, correlation_id. Ne jamais fabriquer de run_id en aval ou court-circuiter cross-run isolation.

## Captures synchronisées
Chaque étape STAR présente une vue correspondant à l'action et au même run, avec source, horodatage, SHA-256 et état de preuve :
1. **Détection** : Grafana, dashboard de l'alerte *firing* ; capture réelle uniquement si navigateur connecté et événement effectivement présent.
2. **Corrélation** : n8n, exécution exacte du workflow 01 (ID réel vérifié).
3. **Enrichissement** : n8n, exécution 02, identité contractuelle, CMDB/RAG (ne pas afficher le payload brut).
4. **Analyse** : n8n, exécutions 03 et 04, diagnostics, critique et limites.
5. **Ticket** : GLPI V1 :8080, ticket lié à l'incident, pas une vue générique ou la mauvaise instance :18080.
6. **Validation humaine** : GLPI, décision HITL vérifiable ; ne jamais cliquer sur une action LIVE.
7. **Simulation** : n8n 06 **uniquement sur une copie isolée et runner attesté simulé**.
8. **Retour au vert** : Grafana, fenêtre de mesures correctement alignée sur l'incident.
9. **Capitalisation** : GLPI, suivi/résolution réellement constatés ; sinon marquer *non démontré*.

Les transitions STAR doivent gérer les états **en attente**, **capture manquante**, **capture réelle qualifiée**, **illustration simulée**. Une illustration générée n'est jamais une preuve produit. Les captures ne sont créées qu'à partir de sessions navigateur autorisées, sans secrets, puis contrôlées et liées à leur étape ; le module `demo.star_snapshot_choreography` vérifie un contrat de métadonnées, il ne prend pas de capture.

## Garde-fous et travaux
- Portail utilisateur unique :17777. Aucune nouvelle exposition réseau.
- Lecture seule par défaut ; import GLPI/Grafana/n8n en dry-run seulement, jamais sur l'instance active sans accord.
- PostgreSQL V1 : 96 objets/62 relations CMDB historiques ; GLPI V1 441 tickets, ne pas publier leurs exports.
- 7 erreurs Analyst localisées à `Prepare Analyst Payload`, catégorie `run_id missing`. Workflow 02 : Webhook → RAG → Canonical Identity → Call Analyst. Ne pas affaiblir le gate.
- Bridge V1 actif mais image containerd incomplète : **aucun restart/recreate**.
- Les visuels conceptuels existants doivent porter un bandeau *ILLUSTRATION NON ISSUE DU RUNTIME*.
- Prochain développement : adaptateur navigateur lecture seule, deep-links par service/run, captures des vraies pages avec conservation d'ID et anonymisation ; tests contractuels sur les trois interfaces et qualification Chromium réelle avant promotion.

## Tests locaux
`python3 -m unittest discover -s tests -p 'test_star_snapshot_choreography.py' -v` (à exécuter dans le checkout). Aucun résultat de test n'est revendiqué par cette note.

## Addendum V2.13.30 — HLD/LLD : frontière de provenance (23 octobre 2026)

**Portée du correctif effectivement poussé :** `demo/star_snapshot_choreography.py` et ses tests contractuels. Aucun service Debian, port, ticket ou workflow V1 n'est modifié.

- **HLD :** capture navigateur (future, autorisée, lecture seule) → manifeste de preuve expurgé → validation syntaxique de provenance → vérification locale PNG/SHA-256/deep link/identité → revue humaine. Aucune étape intermédiaire ne transforme une image synthétique en preuve runtime.
- **LLD :** `validate_capture` refuse désormais `run_id` invalide, horodatage sans fuseau, chemins PNG absolus/relatifs traversants, chemins encodés ou ambigus, URL avec userinfo, fragment, espaces, paramètres non autorisés ou doublons. Les seules clés de requête admises sont `id`, `executionId`, `orgId`, `from`, `to`, `viewPanel`, `var-run_id`. Toute nouvelle clé exige une revue de sécurité et un test.
- **Limite essentielle :** `metadata_complete=True` reste une simple vérification de forme ; `verified_real_capture=False` demeure inconditionnel. Le contrôle d'URL n'est **pas** une preuve de navigation, d'origine authentifiée, d'état métier ou d'anonymisation effective.
- **Rollback :** revert isolé des commits de ce correctif sur la branche de PR, sans toucher à `main` ni aux services. Ne jamais contourner le refus en ajoutant un `run_id` fabriqué.
- **Critères de promotion :** CI STAR PASS sur le SHA exact, revue des liens n8n/Grafana/GLPI V1 :8080, qualification Chromium isolée puis captures réelles opérateur liées à l'événement ; validation métier distincte du statut n8n.

**Continuité V1 02/03 :** l'erreur `RUN_ID_MISSING` n'est pas corrigée par ce contrôle de provenance. La chaîne Webhook → RAG → Canonical Identity → Call Analyst → Prepare Analyst Payload doit être diagnostiquée sur exports et exécutions expurgés, sans mutation de la production.


## V2.13.34 — Contrôle anti-réutilisation des captures

Le collecteur `demo/star_capture_evidence.py` rejette désormais un même SHA-256 PNG utilisé pour deux scènes STAR différentes, même si les chemins et métadonnées sont distincts. Test adversarial : `test_same_png_cannot_prove_two_distinct_scenes`. Il s'agit d'une **vérification d'intégrité locale**, non d'une authentification de la provenance runtime ou de la décision HITL. Une capture n8n réussie ne prouve pas une validation métier.

L'adaptateur navigateur Chromium lecture seule V2.13.34 est **candidat local en attente de publication** : dry-run par défaut, origine et deep link exacts, GET seulement, isolation fixture hors réseau, identité DOM strictement égale, GLPI V1 `:8080`, fenêtre Grafana absolue, PNG/manifestes à revue humaine. Aucun test sur les instances Debian réelles n'est revendiqué. Le portail unique `:17777`, le bridge V1, les tickets, la CMDB et les workflows historiques restent inchangés. La priorité demeure la propagation de `run_id` de 02 Webhook→RAG→Canonical Identity→Call Analyst jusqu'à 03 Prepare Analyst Payload, sans fabrication d'identité.


## Addendum V2.13.38 — liaison stricte des pages (23 octobre 2026)

Le contrôle hors ligne `demo/star_browser_manifest_gate.py` impose désormais la présence d'un gabarit de lien profond **expurgé et propre au service attendu** : Grafana pour détection/vérification, n8n pour exécutions, GLPI V1 pour ticket/HITL/clôture. Un manifeste de scène Grafana qui contient une route GLPI, même valide en soi, est rejeté. Les clés JSON dupliquées sont rejetées ; `event_time_alignment` est obligatoire et reste `UNVERIFIED_REQUIRES_EXTERNAL_EVENT_TIMESTAMP`.

Ce correctif ne constitue ni une capture runtime, ni une preuve d'anonymisation humaine, ni une validation HITL/métier. Les captures authentiques :17777 / n8n / Grafana / GLPI V1 :8080 nécessitent toujours l'adaptateur Chromium autorisé, les pages exactes et une corrélation événementielle indépendante. Le diagnostic V1 02→03 `RUN_ID_MISSING` reste ouvert. Aucun port ou service Debian n'a été modifié.


### Qualification V2.13.42 — identités n8n 02→03 sans alias (23/10/2026)

Le contrat hors ligne `demo/star_n8n_identity_gate.py` impose maintenant **exactement**
`run_id`, `incident_id`, `correlation_id` pour chacun des quatre relevés
`webhook_02`, `rag_02`, `canonical_02`, `prepare_analyst_03`. Tout champ
additionnel (`runId`, `identity`, `run_id_shadow`) entraîne
`IDENTITY_UNVERIFIED` avant toute interprétation. Ce durcissement évite de
qualifier une observation portant simultanément deux identités contradictoires.

Il ne corrige pas le workflow n8n de production : il contrôle uniquement des
observations expurgées. Le succès technique n8n, l'identité métier, la validation
HITL et les effets LIVE restent des validations indépendantes. Aucun changement
Debian, aucun import et aucune capture runtime ne sont requis pour ce contrôle.


## Addendum V2.13.44 — ancrage temporel indépendant (23 octobre 2026)

Le nouveau `demo/star_event_capture_alignment.py` confronte, **hors réseau**, les manifestes Chromium et PNG déjà qualifiés à une **ancre d'événement externe fournie séparément**, avec les mêmes `run_id`, `correlation_id`, `event_ref`. Tolérance bornée par défaut : 3 s d'écart d'horloge et 120 s de délai après l'événement. Les captures hors fenêtre, les ancres manquantes, les identités contradictoires et les mélanges de provenance fixture/runtime sont refusés. La source d'événement et son SHA-256 déclaré ne sont **pas authentifiés** par ce module ; le résultat reste `CONSISTENT_UNAUTHENTICATED`, sans validation HITL ou métier.

HLD/LLD, limites, rollback et qualification : `docs/demo/STAR-EVENT-CAPTURE-TIME-ALIGNMENT-V21344.md`. CI offline dédiée : `.github/workflows/star-event-capture-alignment-offline.yml`. Aucune navigation Debian, aucun ticket ni conteneur modifié.
