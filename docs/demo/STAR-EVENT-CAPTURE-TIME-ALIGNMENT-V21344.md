# ACME STAR — vérification temporelle indépendante V2.13.44 (23 octobre 2026)

**Statut : module et tests offline sur captures de fixtures synthétiques ; aucune capture de runtime Debian réalisée.**

## HLD — frontières de confiance

Portail unique `:17777` → storyboard STAR → manifeste Chromium `star-browser-evidence/v1` → validateur `star_browser_manifest_gate` (identité canonique, service/vue, PNG/CRC/SHA256, provenance, chronologie) → **nouveau** `star_event_capture_alignment` (ancre d'événement indépendante, identité et fenêtre temporelle) → revue humaine. Les preuves n8n, Grafana et GLPI V1 `:8080` restent **non authentifiées** par ces contrôles offline. La correspondance temporelle ne prouve ni état métier, ni HITL, ni résolution, ni autorisation LIVE.

## LLD — contrat strict

`verify_event_capture_alignment(root, expected, filenames, anchors, max_delay_seconds=120, clock_skew_seconds=3)` n'effectue aucun accès réseau. `expected` provient de l'ingress canonique indépendant ; `anchors` doit provenir d'un export événementiel **distinct** de la capture. Une ancre par scène fournie, avec **exactement** `run_id`, `correlation_id`, `event_ref`, `event_at` (ISO8601 avec fuseau), `source_kind` et `source_sha256` (hexadécimal minuscule, 64 caractères). La provenance `ISOLATED_FIXTURE_EVENT` correspond uniquement à une capture `ISOLATED_TEST_FIXTURE` ; `OPERATOR_EVENT_LOG_UNREVIEWED` correspond uniquement à `OPERATOR_BROWSER_UNREVIEWED`.

L'algorithme contrôle d'abord le manifeste et le PNG via la passerelle existante, puis refuse toute identité contradictoire, ancre absente/supplémentaire, source d'une autre provenance, date sans fuseau, capture trop précoce ou trop tardive. Tolérance par défaut : capture au plus **3 secondes avant** l'événement (dérive d'horloge) et **120 secondes après**. Paramètres bornés : 0–10 s de dérive et 1–3600 s de délai ; pas de booléens. Aucune valeur d'identité n'est fabriquée.

Le rapport `CONSISTENT_UNAUTHENTICATED` inclut le délai par scène et les drapeaux `runtime_authenticated=false`, `business_validated=false`, `human_approval_authenticated=false`, `live_remediation_authorized=false`, `independent_event_source_authenticated=false`. Le SHA-256 déclaré de la source événementielle est **syntaxiquement vérifié mais non recalculé** ; le journal externe n'est pas fourni à ce module. Le module ne signe aucune preuve et ne doit pas être utilisé pour approuver une action.

## Qualification et déploiement

Tests offline : `python3 -m unittest discover -s tests -p 'test_star_event_capture_alignment.py' -v`. CI isolée sans secrets et sans accès au runtime. Avant de collecter une capture authentique : revue opérateur de l'URL exacte, des GET explicitement autorisés et des sélecteurs de masquage ; collecte de l'événement depuis une source indépendante avec horloge qualifiée ; revue manuelle de l'anonymisation et de l'identité. Aucun navigateur ne doit contacter Debian dans les CI. N'ouvrir aucun port, ne modifier ni les workflows V1 ni la CMDB/tickets, ne redémarrer jamais le bridge V1. Simulation de remédiation uniquement.

**Rollback :** revert des nouveaux fichiers sur la branche PR ; `main` et les conteneurs de production restent inchangés.
