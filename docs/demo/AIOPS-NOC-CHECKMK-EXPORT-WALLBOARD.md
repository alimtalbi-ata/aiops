# AIOps — Interface NOC Checkmk de lecture des exports hors ligne

## Livraison
`demo/noc_checkmk_offline_wallboard.py` transforme le modèle de consolidation `aiops-noc-checkmk-merged-offline-v1` en une page HTML autonome avec filtres de sévérité, une ligne par équipement, séparation disponibilité et état consolidé, et des panneaux affichant les contrôles de services. La page indique obligatoirement la date de capture et l'âge lors de la validation.

## Exécution
Avec deux fichiers JSON déjà normalisés et correspondant au même lot :

```bash
python -m demo.noc_checkmk_offline_wallboard host-export.json service-export.json --output /tmp/checkmk-export-noc.html
```

La sortie HTML est autonome, sans API ni requête HTTP, et refuse l'écrasement d'un fichier existant. Les champs provenant des exports non fiables sont échappés, et les nombres de contrôles sont recroisés avec le manifeste.

## Contrat de vérité
Le bandeau permanent `EXPORT HORS LIGNE NON AUTHENTIFIÉ` interdit la confusion avec la production. La page refuse un modèle attestant faussement un runtime actif, conserve les horodatages fournis sans les transformer en mesure temps réel, et n'autorise aucune modification dans Checkmk/Thruk, GLPI, n8n, Grafana ou le serveur Debian.

## Qualification
`tests/test_noc_checkmk_offline_wallboard.py` ajoute quatre tests pour rendu hôtes/services, échappement du contenu hostile, refus d'une fausse attestation LIVE et refus des totaux falsifiés. Le workflow `aiops-rag-ops-fixtures.yml` les inclut.

**Limite :** ce HTML n'est pas encore connecté à la route `:17777` et ne constitue pas un test NOC métier LIVE. Reprendre la configuration historique Checkmk/Thruk et qualifier les connexions de lecture seule avant toute intégration.
