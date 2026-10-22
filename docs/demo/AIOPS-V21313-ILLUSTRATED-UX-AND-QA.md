# AIOps V2.13.13 — Démonstration illustrée

## Expérience
Le théâtre STAR conserve 12 scènes, chacune avec un message principal. Le sélecteur **Public métier/technique** ajuste le texte central. Le bouton **Sources et limites** révèle, sans l'afficher en permanence, les réserves et la provenance de la scène. Un panneau **Comprendre cette étape** fournit une explication facultative.

Trois dessins SVG vectoriels intégrés au fichier HTML remplacent les simples encadrés texte : terminal du service métier, graphe Fibre Channel représentant le SAN, bouclier de décision. Le schéma met en évidence le domaine concerné à chaque scène, anime discrètement le flux d'information, et affiche une légende contextuelle. Ce sont des illustrations fictives et non une cartographie CMDB réelle.

## Accessibilité / sobriété
Pas de bibliothèque d'animation ni de requête externe. SVG local, aria-hidden sur les icônes décoratives, description textuelle du schéma, panneau details/summary clavier-natif. Le CSS respecte prefers-reduced-motion. La vue reste lisible sans animation et conserve le mode présentateur, pause, lecture automatique et écran mobile.

## Qualification attendue
1. Récupérer depuis GitHub l'asset V2.13.13 et `tests/browser/qualify_v21313_star.py` dans une copie de la source V2.13.12.
2. Exécuter Playwright sur `file://` avec le script V2.13.13 (mode public, provenance, SVG, focus, détail, mobile).
3. Rejouer `tests/browser/qualify_v21312_star.py` sur ce même asset pour les tests chronométrés, pause et mobile.
4. Construire l'image isolée `aiops2-portal:v21313` et vérifier l'asset; ne déployer sur le portail unique 17777 qu'après PASS, sauvegarde/rollback et validation des règles de sécurité.
5. Après bascule, retester Chromium sur /demo/star et HTTP 403 sur le replay historique.

## État réel
Code et tests de V2.13.13 publiés sur branche de PR #36, mais **aucun test Chromium, build Docker ni déploiement V2.13.13 effectué dans cette itération**. Le déploiement observé le plus récent reste V2.13.12, qualifié 13/13 dans Chromium sur 17777.

## Garanties
Aucun nouveau port, aucun backend, aucune donnée Core, aucun appel DGX, aucune remédiation LIVE, aucune authentification affaiblie. Distinction permanente `SIMULATED_TARGET` / `OPERATOR_SUPPLIED_EXPORT`.
