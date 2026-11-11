# Inventaire Docker rootless AIOPS2 — utilisation

Le script `scripts/ops/inventory_rootless_one_stack.py` fournit un état **en lecture seule** des conteneurs (actifs et arrêtés), volumes, réseaux, montages, ports publiés, images et labels Compose utiles. Il génère une matrice provisoire de traitement.

## Sur SRV-DEB-05

Depuis une session shell de l'utilisateur `aiops` (sans `sudo docker`), dans une copie à jour du dépôt :

```bash
docker context show
python3 scripts/ops/inventory_rootless_one_stack.py --out "$HOME/aiops2-audit-$(date +%Y%m%d)"
```

La commande refuse le contexte autre que `rootless`, un utilisateur root, ou un DockerRootDir différent de `$HOME/.local/share/docker`.

Fichiers locaux créés (permissions 0600 dans un dossier 0700) :
- `inventory.json` : métadonnées structurées des conteneurs, montages, volumes et réseaux.
- `inventory.md` : matrice conteneur/état/projet/service/classification provisoire.

Le script **ne lit pas** les valeurs d'environnement des conteneurs, le contenu des volumes, les fichiers secrets, les logs ni les variables Compose. Il n'exécute aucune mutation Docker.

## Règles de confidentialité

Les chemins de montages, noms d'hôtes, conteneurs et topologie peuvent néanmoins être sensibles. **Relire et masquer** les données avant de les publier dans GitHub. Ne jamais committer `inventory.json` automatiquement, ni le contenu de `.env`, `bridge.token`, les mots de passe ou les tokens.

## Règles d'interprétation

- `RUN_CANDIDATE_VERIFY` : projet rebuild ou metrics-cutover, à qualifier avant intégration.
- `STOP_CANDIDATE_AFTER_VALIDATION` : projet de test E2E, v27 ou démo; ne pas arrêter avant extraction des capacités et vérification des dépendances.
- `UNKNOWN` : ownership non fiable, absent ou autre projet; décision manuelle.

La classification ne représente **jamais un ordre d'arrêt**. La matrice définitive RUN/STOP/KEEP/REMOVE doit être approuvée avec les sauvegardes, tests, plan de rollback et inventaire des dépendances.

Références : issue #555, PR #635, PR #636.
