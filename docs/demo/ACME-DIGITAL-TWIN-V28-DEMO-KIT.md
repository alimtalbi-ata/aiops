# ACME Digital Twin — kit de démonstration V2.8 (candidat)

**Statut : candidat, démonstration de bout en bout non encore qualifiée ; NO-GO production.**  
**Exclusivement pour un environnement de qualification indépendant.**  
**Auteur : Abdelhalim Talbi.**

## Objectif
Montrer une anomalie SAN synthétique sur `ACME-SAN-FABRIC-A`, la topologie de dépendances, les observations mesurées/simulées, l'analyse et sa critique, puis un refus de remédiation avec une trace transactionnelle vérifiable.

## Inventaire d'API confirmé par lecture des sources (pas encore qualification E2E ACME)
| Service | Route | Objectif |
|---|---|---|
| Core | `GET /health` | disponibilité et accès à PostgreSQL |
| Twin | `GET /health` | disponibilité |
| Twin | `GET /api/twin/summary` | nœuds, arêtes, états |
| Twin | `GET /api/twin/graph` | nœuds et dépendances |
| Twin | `GET /api/twin/nodes` | inventaire |
| Twin | `GET /api/twin/impact/ACME-SAN-FABRIC-A` | propagation d'impact suivant les arêtes orientées |
| Twin | `GET /api/twin/at?known_at=<ISO-8601>` | historique bitemporel selon les données persistées |
| Twin | `POST /api/twin/synthetic-event` | actions synthétiques `SET_STATE` ou `OBSERVE`; nécessite un run et un jeton |
| Simulator | `GET /api/scenarios` | catalogue |
| Simulator | `POST /api/demo/golden` | déclenchement de la démo; **ne pas lancer sans stack isolée et autorisation** |
| Core | `POST /api/runs/{rid}/critic-denial-resume` | reprise de refus Critic après persistance de l'événement |

## Storyboard cible (non exécuté intégralement)

1. **Préflight** — vérifier identités des conteneurs, réseaux et bases isolés; versions d'image et migrations; authentification; aucune publication de ports; aucun lien avec V2.6/V2.7.
2. **État nominal** — afficher résumé, graphe et chemin d'impact vers le service ACME de paiement; photographier les comptes initiaux.
3. **Injection DEMO** — sur un run synthétique unique, dégrader le nœud SAN et consigner l'observation `fc_errors=184 errors/min` et `health=0.42`. Les valeurs sont **fictives, paramètres de démonstration**, et ne constituent pas des mesures réelles.
4. **Diagnostic** — corréler analyst/critic aux evidence IDs et au graphe; afficher confiance, sources, incertitudes, causes alternatives.
5. **Gate** — Critic rejette l'analyse : état `BLOCKED`, aucune remédiation LIVE, aucune approbation HITL fabriquée. Afficher journal, reçu, outbox et empreinte.
6. **Résilience** — répéter la requête de reprise; vérifier `idempotent=true`, empreinte stable, aucune écriture supplémentaire. Prévoir campagne de concurrence et perte de réponse.
7. **Retour à l'état initial** — uniquement sur dataset synthétique, via procédure de reset qualifiée; ne jamais lancer un reset générique contre les stacks opérationnelles.

## Qualification vérifiée (exécution rapportée sur Debian isolée le 20/10/2026)
- QF-178/179 : **35/35 tests unitaires** sur l'hôte de qualification (et non GitHub Actions).
- QF-185 : image Core `aiops2-core:v28-qf185`, import `core.main` PASS après correction locale.
- QF-186 : Core `GET /health` HTTP 200.
- QF-187 : endpoint sans jeton 401, jeton erroné 401, jeton correct et run inexistant 409.
- QF-188 : reprise via HTTP réel, rejouée sans doublon : `BLOCKED|4|COMMITTED|2|1|1`.
- QF-189 : 8 requêtes concurrentes, **1 transaction + 7 rejouements**, même état final.
- QF-190 : connexion client fermée sans lire la réponse; commit constaté puis nouvelle requête idempotente, sans doublons.
- **Non qualifié** : E2E complet du Digital Twin, accès à un provider IA réel, reprise Temporal après panne de Worker/Core, rollback de topologie synthétique, interface visuelle, sauvegarde vidéo et tests de production.

## Invariants de sécurité
- `DEMO`, `REPLAY` ou `STORY` exclusivement; ne pas activer `LIVE`.
- Données ACME explicitement synthétiques; preuves réelles distinguées des valeurs injectées.
- Aucun réseau, volume ou conteneur de V2.6/V2.7 n'est manipulé.
- Aucun jeton dans les logs, captures ou fichiers versionnés.
- PR #35 reste **draft**. Aucune fusion vers main ni approbation automatique.

## Conditions avant une démonstration qualifiée
Un pipeline isolé doit produire les preuves suivantes : version/sha des images, santé de chaque service, catalogue et graphe de dépendance cohérents, horodatages du scénario, traces d'appels Analyst/Critic avec provenance, décisions Policy/HITL, états du journal et outbox, rejeu et concurrence, captures réelles des interfaces, rapport d'échec et procédure de nettoyage.

Ce fichier est une **documentation de démonstration** et ne doit pas être présenté comme une capture, un enregistrement vidéo ou un rapport d'E2E exécuté.


## Lot DEMO-OFFLINE (21 octobre 2026) — générateur autonome

**Objectif : fournir immédiatement une démonstration consultable sans accès à Debian ou aux stacks opérationnelles.** Cette démo est une maquette HTML interactive avec nœuds/relations ACME **entièrement fictifs**, timeline illustrative et blocage Policy simulé. Elle ne réalise ni appels DGX ni propagation d'effet réelle.

Depuis la racine d'un clone de la branche V2.8 :

```bash
python3 tools/build_acme_offline_demo.py --output reports/acme-demo-offline.html
python3 -m unittest discover -s tests -p 'test_v28_acme_offline_demo.py' -v
```

Ouvrir ensuite `reports/acme-demo-offline.html` dans un navigateur. Le document est autonome et ne nécessite aucun serveur Web. Il ne contient aucun jeton et ne contactera ni Core, ni PostgreSQL, ni Digital Twin de production. Les nœuds sont marqués dégradés ou sains selon un dataset de démonstration fictif; tous les chiffres éventuels sont *illustratifs*.

**Recette minimale :** HTML généré, graine de topologie cohérente, recherche de nœud, filtres site/état, zoom et restauration, visualisation des impacts du jeu synthétique, mention « NON QUALIFIÉ production », pas de chargement externe, pas de bouton LIVE.

**Distinction nécessaire :** cette maquette utilisable n'est pas la qualification intégrée Temporal + DGX + Evidence/Policy. Pour la démo connectée à la stack V2.8, continuer à utiliser uniquement le profil E2E isolé et son jeu de tests; ne jamais activer `AIOPS_DEMO_LAUNCH_ENABLED` dans un environnement opérationnel.
