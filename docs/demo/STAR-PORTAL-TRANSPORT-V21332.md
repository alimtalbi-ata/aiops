# Export cinématique STAR vers le portail 17777 — V2.13.32

Le module `demo/star_portal_transport.py` fournit un **format JSON stable de lecture seule**, fondé sur un manifeste de captures vérifié en local.

## Utilisation
```bash
python3 -m demo.star_portal_transport /chemin/prive/manifest.json --root /chemin/prive --scenario SAN_FABRIC_P1 --output /chemin/prive/storyboard.json
python3 -m unittest discover -s tests -p 'test_star_portal_transport.py' -v
```

Le JSON comporte neuf scènes et les libellés en français (`missing`, `simulated`, `integrity_checked`). Toute action remédiatrice est interdite. Le contenu n'affirme pas que la capture vient d'un runtime authentifié ; seule l'intégrité des octets peut être vérifiée.

**Précision :** aucun endpoint dans le portail actuellement déployé sur 17777 n'a été ajouté. La fusion dans le template/runtime STAR nécessite une revue de sa structure réelle, des identifiants de run et du mécanisme d'anonymisation. Ne jamais utiliser un fichier généré en environnement isolé comme preuve d'un navigateur de production.

## CI et sécurité
Le script refuse l'écrasement d'un export et ne fait aucun HTTP, aucune commande Docker, aucun appel GLPI, Grafana, n8n ou IA. Captures fictives et preuves manquantes restent distinguées. Tout manifest contenant des données confidentielles doit rester hors Git.

Prochaine étape : adapter la vraie route de consultation STAR en lecture seule, puis tester Chromium avec la page exacte de chaque application, ainsi que les états sans capture.
