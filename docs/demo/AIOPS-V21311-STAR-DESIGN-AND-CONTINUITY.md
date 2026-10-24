# AIOps V2.13.11 — STAR Mission Control

## Objectif de conception
Une seule page de démonstration, 12 étapes, **une idée centrale par écran**, avec narration courte et un panneau latéral qui explique pourquoi la scène compte. Aucun deuxième portail; cible future `/demo/star` sur l'unique portail `:17777`.

## Parcours
1. Paiement ralenti
2. Dépendances SAN
3. Qualifier sans agir
4. Corréler les signaux
5. Analyst propose
6. Critic conteste
7. Risque et impact
8. Policy bloque
9. Décision humaine
10. Communication
11. Preuves
12. Résilience mesurable

Chaque scène contient : titre court, explication métier, position dans le schéma, justification architecturale, limites/provenance, question de comité. Le détail technique n'occupe pas la scène principale.

## Interaction
Précédent/suivant, sélection des 12 scènes, lecture/pause, restart, trois vitesses, progression, clavier gauche/droite/Home/End/Espace. Lecture stoppée lorsque l'onglet n'est pas visible. Conception responsive, focus visible et réduction des animations pour accessibilité.

## Sécurité
`SIMULATED_TARGET` affiché en permanence. Aucune URL d'écriture, appel Core/DGX, historique ni véritable approbation HITL. L'asset statique se situe sous `app/portal/public_demo_assets/AIOPS-EXECUTIVE-THEATER-PUBLIC.html`. Le routeur public V2.13.10 sert la page en lecture seule et reste fail-closed si l'asset manque.

## GitHub et déploiement
Branche de continuité et PR draft #36. Le code ajouté à GitHub n'est pas encore incorporé au conteneur Debian actif V2.13.10. Ne pas toucher au conteneur ou à sa configuration avant reprise opérateur.
1. Tester l'HTML isolé et l'interaction Chromium avec `tests/browser/qualify_v21311_star.py`.
2. Réconcilier les sources du kit Debian V2.13.10 avec les sources GitHub. Le fichier `portal/main.py` versionné peut diverger de l'image déployée.
3. Construire en staging non publié, vérifier que l'ancien portail 17777 est intact, puis planifier un remplacement unique de service après validation utilisateur.
4. Publier les preuves réelles dans une release cumulative sans inventer de captures ou tests.

## Qualité restant à établir
Test des boutons et du clavier en Chromium non encore exécuté dans cette itération; il est seulement ajouté au dépôt. Vérifier les labels, tailles mobiles, pause réelle de l'autoplay et débordements. Aucun score DGX ni gain opérationnel prouvé.
