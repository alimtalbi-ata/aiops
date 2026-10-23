# STAR screenshot evidence collector — V2.13.31

Le module `demo/star_capture_evidence.py` vérifie **hors ligne** des captures PNG existantes associées aux neuf scènes de `demo/star_snapshot_choreography.py`.

## Exécution

Créer un manifeste JSON **privé** contenant `run_id` et `captures` (dictionnaire par scène). Pour chaque scène : `service`, `view`, `proof_state=captured`, `run_id`, `captured_at` avec timezone, `source_url` sans secrets, `screenshot_path` relatif à `evidence/`, `sha256` hexadécimal. Ne jamais y mettre token, cookie, en-têtes ou URL avec paramètres sensibles.

```bash
python3 -m unittest discover -s tests -p 'test_star_capture_evidence.py' -v
python3 -m demo.star_capture_evidence /chemin/prive/manifest.json --root /chemin/prive
```

La sortie est un **rapport d'intégrité local**, non une attestation d'authenticité de la capture ni de l'exécution métier. Toutes les scènes manquantes sont explicites. Aucun accès réseau, aucun clic sur GLPI/n8n/Grafana et aucune modification de ticket, workflow ou conteneur.

## Intégration cinématique

Garde-fou avant toute intégration UI STAR : les séquences doivent afficher `missing`, `simulated`, `integrity_checked`, jamais `real verified` automatiquement. L'opérateur doit capturer la vraie page correspondant au run/ticket/exécution, puis vérifier visuellement, anonymiser, calculer SHA256 et rattacher au manifeste. Les illustrations générées restent clairement marquées comme fictives.

## Limites et qualification

PNG vérifié par signature/IHDR/taille/SHA256 ; le module ne réalise pas d'analyse visuelle, de validation d'identité dans le DOM, ni de navigateur E2E. Il ne peut pas prouver une action HITL ou une remédiation réelle. Aucun résultat de tests ou CI n'est présumé tant que les commandes correspondantes n'ont pas été exécutées sur le checkout.

Rollback : supprimer uniquement ce module, son test et cette note depuis la branche de PR.
