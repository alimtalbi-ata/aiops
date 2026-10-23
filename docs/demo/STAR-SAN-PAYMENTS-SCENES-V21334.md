# STAR — scénarios SAN P1 et Payments P2 (cinématique V2.13.34)

## Implémentation

`demo/star_scene_scripts.py` ajoute un scénario narratif **fictif et déterministe** par incident, raccordé au JSON produit par `demo.star_portal_export`. Il définit, pour chaque étape, la bonne application, la vue attendue et la phrase de démonstration. Il valide l'ordre des neuf étapes, l'adéquation application/vue, l'absence d'actions autorisées et l'absence de prétendue authentification du runtime.

- **SAN_FABRIC_P1** : perte de chemin FC Brocade → impact potentiel multipath/Payments → analyse et critique → ticket → HITL → simulation → observabilité → clôture conditionnelle.
- **PAYMENTS_P2** : hausse de latence applicative → corrélation avec le stockage → hypothèses alternatives DGX/Critic → ticket → policy → simulation → comparaison SLO → capitalisation.

Les libellés indiquent **ce qu'il faut montrer**, jamais que l'événement est réellement présent. Les pièces attendues correspondent aux vues n8n/Grafana/GLPI fixées par `star_snapshot_choreography.py` ; leur disponibilité est déterminée par le manifeste, pas par le scénario narratif.

## Qualification

```bash
python3 -m unittest discover -s tests -p 'test_star_scene_scripts.py' -v
```

La CI dédiée est raccordée, résultat à contrôler sur le dernier SHA. Aucune capture réelle ni session navigateur n'a été réalisée dans cette modification ; aucun déploiement sur le portail :17777.

## Intégration suivante

Afficher les scènes dans l'interface du portail unique en lecture seule, afficher une indication explicite de preuve manquante/fictive/contrôlée et ajouter des vues navigateur après qualification E2E isolée. Ne pas exposer de nouvelles URL publiques, ne pas faire de POST API, ne pas redémarrer le bridge V1 ni confondre image fictive et preuve du système.
