# Charte UI cible — portails AIOps 2.0 / ACME Digital Twin

**Auteur : Abdelhalim Talbi.** **Référence graphique :** fichier utilisateur `Timeline AIOps : de l’incident à la remédiation.html` (fourni le 20/10/2026). **Statut :** guide d'implémentation / prototype de composants; non-recette UI Windows.

## Ce que l'on reprend du modèle HTML

- Hero bleu nuit / halos violets et verts, titre à dégradé multicolore.
- Typographie system-ui, responsive jusqu'au smartphone, content area centrée.
- KPI sous forme de cartes aux accents colorés, panneaux arrondis, chips/pills, logs monospace contrastés.
- Timeline verticale (événement, état, stage, date, clé), rail, pastilles de phases, progression.
- Navigation cohérente, sections découpées, modes clair/sombre et `prefers-reduced-motion`.
- Codes couleur sémantiques : rouge incident/refus, orange observation, violet analyse, bleu orchestration/ticket, vert validation, vert olive vérification/résolution.

**Ne pas reprendre comme faits** les valeurs 4 s, 21 s, 2 min 33, 14→1, latence 48 ms, SSD-07, « ticket résolu » ou « remédiation réussie » présentes dans l'exemple. Ce sont des **données illustratives**, non des mesures de la plateforme.

## Architecture technique UI

Le module partagé `app/portal/ui_theme.py` définit `shell(page,title,description,body,mode)`, `panel()`, `table()` et `pretty()`. La vue `app/portal/main.py` compose toutes les pages à partir de ce shell. Le HTML échappe les valeurs issues de la base et des API avant insertion. Les CSS sont centralisés, sans dépendance CDN. Les rendus serveur n'intègrent pas de jetons internes dans le navigateur.

Une refonte ultérieure peut extraire le CSS et les composants en fichiers statiques versionnés (cache CSP, tests snapshot visuels). La structure actuelle facilite ce futur découpage.

## Matrice complète des pages cible

| URL actuelle | Page | Données utilisées / statut | Suite fonctionnelle |
|---|---|---|---|
| `/` | Operations cockpit | Core dashboard + Twin summary + runs | filtres temps, erreurs / SLO |
| `/runs` | Incidents & Runs | Core /api/runs | recherche, pagination, détail run |
| `/timeline` | Timeline | événements Core du premier run courant | choix du run, flux live et replay |
| `/twin` | Digital Twin ACME | Twin summary, graph, impact + tables | graphe interactif, zoom, chemin critique, bitemporel |
| `/evidence` | Preuves et observabilité | guide / état explicite, pas d'agrégation API | evidence API, provenance, Loki/Prometheus |
| `/policy` | Policy & HITL | runs BLOCKED / WAITING | gates, acteurs, approbations authentifiées |
| `/copilot` | Copilot | proxy API /api/copilot préexistant | citations, critic challenge, RBAC, historique |
| `/qualification` | Qualification & audit | matrice documentaire des tests rapportés | lecture des manifestes CI et cas d'essai |
| cible | Remédiation et vérification | **NON IMPLÉMENTÉ** | playbooks signés, scopes, approvals, preuve d'effet, rollback |
| cible | CMDB/Change | **NON IMPLÉMENTÉ** | écarts configuration, changement récent, impact |
| cible | Administration & sécurité | **NON IMPLÉMENTÉ** | RBAC, utilisateurs, journaux d'accès, secrets serveur |
| cible | Demo Studio | **NON QUALIFIÉ** | dataset seedé, start/stop/reset isolés, snapshots réels |

**Important :** « page créée » ne signifie pas « fonctionnalité sous-jacente qualifiée ». Les pages Evidence et Policy sont pour l'instant principalement de lecture/documentation et ne réalisent pas de modification d'état. Aucun graphique Twin interactif n'est revendiqué.

## Critères de qualité UI

1. Chaque page présente un titre, un mode, une source de données, sa disponibilité et sa fraîcheur si connue.
2. Données manquantes = `INCONNU` ou `NON QUALIFIÉ`; jamais une valeur simulée sans badge « SYNTHETIC ».
3. Action dangereuse désactivée par défaut; backend applique aussi l'autorisation (ne jamais dépendre seulement du bouton désactivé).
4. Clavier et focus visible; respect des préférences d'animation; contrôle de contraste.
5. Pas d'HTML brut non échappé depuis des incidents, modèles ou journaux.
6. Les animations sont purement cosmétiques; état machine lisible sans elles.
7. Timeline fondée sur `sequence` et `occurred_at` canoniques, pas sur des timestamps fictifs.
8. Séparer les statuts d'activité, de santé, de preuve et de qualification.
9. Optimisation cible desktop 1920x1080, laptop et écran mobile 390px; tests screenshots réels avant promotion.
10. Rechercher des performances raisonnables avec pagination, rendu partiel, non-blocage des appels amont.

## Audit UI et critères d'acceptation non encore satisfaits

- [ ] Test d'import Python / FastAPI du nouveau portail dans GitHub Actions.
- [ ] HTTP GET 200 de chaque page, après installation et avec Core/Twin simulés.
- [ ] Tests anti-injection HTML / XSS sur sorties utilisateur.
- [ ] Vérification WCAG de base et clavier (Playwright ou navigateur réel).
- [ ] Captures écran réelles de chaque page, non substituées par maquettes.
- [ ] Test visuel responsive desktop/tablette/mobile, thème clair/sombre.
- [ ] Test complet Digital Twin ACME, qualité graphe/impact.
- [ ] Découplage proxy Copilot et authn/RBAC pour actions accessibles depuis le navigateur.
- [ ] Autorisation backend sur toute action DEMO ou LIVE ; refus par défaut.
- [ ] Mise en page toutes les autres interfaces éventuelles hors `app/portal` après inventaire.

## Feuille de route

V2.8-A — Shell commun et routes de consultation. V2.8-B — composant timeline animé sur événements réels, graph Twin interactif accessible. V2.8-C — pages Evidence/Policy branchées aux API réelles avec RBAC. V2.8-D — Demo Studio qualifié ACME à graine fixe, capture testée. V2.9 — consolidation ergonomie, captures et campagne utilisateur.

## Adaptation par rapport au HTML fourni

Le code référent était une timeline statique illustrant un incident SSD et des délais fixes. Le portail adapte **le langage visuel** à une source serveur canonique : pages distinctes, valeurs dynamiques ou état INCONNU, thèmes, navigation et capacités limitées tant que les gates ne sont pas qualifiés. Il ne reproduit ni une métrique arbitraire ni une exécution automatique de remédiation.


## Décision de sécurité UI/Backend — QF191 (21/10/2026)

La page Cockpit conservait un bouton DEMO désactivé mais la route `POST /api/demo` restait appelable directement. **Correction sur branche V2.8 :** route bloquée par défaut (HTTP 403), lancement autorisé uniquement après `AIOPS_DEMO_LAUNCH_ENABLED=true` et validation de `Authorization: Bearer` contre le jeton interne configuré (comparaison constant-time). Tests automatisés négatifs couvrant le défaut d'autorisation et les jetons erronés; leur passage CI doit être confirmé séparément. Cette route demeure exclusivement destinée à une stack synthétique isolée. La présence d'un flag d'activation ne suffit pas à qualifier une mise en production. Une authentification d'utilisateur/RBAC, protection CSRF et scope de demo restent nécessaires avant exposition externe.

### État de qualification UI

Le workflow CI V2.8 sur le SHA `68c8385` a été observé **SUCCESS** pour `AIOps quality gates` et `V2.8 Core qualification`. Ceci qualifie les jobs CI exécutés, **pas** une recette browser ni Digital Twin E2E. Le test ajouté sur la route DEMO après ce SHA nécessite une nouvelle vérification sur son commit propre.


## Incrément QF192 — Graph Twin et correction CI (21/10/2026)

- Route `/twin`: graphe SVG orienté, navigation au clavier, recherche et dépendances directes, borné à 120 nœuds/300 relations affichés. Le graphe suit le contrat `GET /api/twin/graph`.
- Le résultat de `GET /api/twin/impact/ACME-SAN-FABRIC-A` marque uniquement les nœuds explicitement renvoyés par le service Twin. Si la réponse est manquante ou invalide, le statut d'impact demeure `INCONNU`, jamais calculé par supposition côté UI.
- L'ancienne CI globale échouait après la sécurisation du endpoint `POST /api/demo` : tests unitaires et E2E supposaient un lancement sans jeton. Correction : tests unitaires activent explicitement le mode DEMO et transmettent le jeton de qualification; l'override `.github/compose.e2e.yml` active la démo uniquement dans le profil jetable et le script E2E obtient le jeton directement depuis le conteneur Portal. Aucune réouverture du endpoint non authentifié en production.
- Validation en cours sur les nouveaux commits : **ne pas déclarer SUCCESS avant confirmation GitHub Actions**. Toute CI rouge est un point bloquant.
- Restent non qualifiés : rendu navigateur réel, WCAG, grands graphes, performance et graphe complet ACME connecté à une campagne synthétique transactionnelle.


## Incrément QF193 — exploration du graphe (21/10/2026)

Le composant SVG Digital Twin ajoute un zoom borné (facteur 0,65 à 3), un filtre texte, des facettes site/état dérivées des nœuds transmis, et une réinitialisation globale. Les filtres s'appliquent seulement aux nœuds du sous-ensemble affichable : cette vue n'est pas un inventaire exhaustif d'un grand graphe. Les relations orphelines ne sont pas dessinées. Les états/impacts restent issus de la réponse Twin ; les couleurs ne constituent pas une preuve de diagnostic.

Qualification requise : tests unitaires GitHub, navigation clavier, rendu navigateur réel et vérification de l'échantillonnage sur plus de 120 nœuds. Ne pas promouvoir sans E2E complet.
