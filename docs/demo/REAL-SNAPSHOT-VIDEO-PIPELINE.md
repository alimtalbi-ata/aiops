# Video de démonstration unique avec captures opérateur

## Réutilisation

La PR #36 contient déjà `demo/generate_demo_video.py`, le workflow `generate-demo-video.yml` et les contrats STAR de capture/manifestes. Ils constituent la base du rendu **synthétique** et des contrôles de provenance. Ne pas importer aveuglément toute la branche PR #36. Le script ci-dessous ajoute un chemin distinct pour des PNG fournis par un opérateur; il ne capture pas lui-même le runtime.

## Objectif

Une vidéo MP4 unique retraçant les vues du portail, Thruk, Grafana, n8n et GLPI. La capture de chacune doit être obtenue dans une session autorisée, sur l'environnement concerné, à un instant documenté. Les captures ne prouvent pas à elles seules la réalité des données, l'identité de la session ou la causalité entre systèmes.

## Manifeste d'entrée

Stocker cinq fichiers PNG dans un répertoire privé et un manifeste JSON hors Git. Format minimal :

```json
{
  "schema_version": 1,
  "provenance": "OPERATOR_SUPPLIED_UNATTESTED",
  "captures": [
    {"service":"portal","file":"portal.png","sha256":"<sha256 réel>","captured_at_utc":"2026-10-27T19:00:00Z","source_url":"http://10.79.94.202:17777/"},
    {"service":"thruk","file":"thruk.png","sha256":"<sha256 réel>","captured_at_utc":"2026-10-27T19:00:00Z","source_url":"<URL réellement vérifiée>"},
    {"service":"grafana","file":"grafana.png","sha256":"<sha256 réel>","captured_at_utc":"2026-10-27T19:00:00Z","source_url":"<URL réellement vérifiée>"},
    {"service":"n8n","file":"n8n.png","sha256":"<sha256 réel>","captured_at_utc":"2026-10-27T19:00:00Z","source_url":"<URL réellement vérifiée>"},
    {"service":"glpi","file":"glpi.png","sha256":"<sha256 réel>","captured_at_utc":"2026-10-27T19:00:00Z","source_url":"<URL réellement vérifiée>"}
  ]
}
```

Les valeurs entre chevrons sont des placeholders, **pas des preuves**. Les captures doivent être masquées pour retirer identifiants, tokens, données personnelles et secrets, puis leur hash recalculé après masquage. L'URL n'est qu'une métadonnée déclarative, non vérifiée par le script.

## Commandes

```bash
python3 demo/evidence_video.py --manifest /chemin/prive/manifest.json --evidence-root /chemin/prive/captures
python3 demo/evidence_video.py --manifest /chemin/prive/manifest.json --evidence-root /chemin/prive/captures --output /chemin/prive/demo-preuves.mp4
```

Prérequis : Python 3 et ffmpeg avec libx264. Par défaut chaque capture dure six secondes (30 secondes au total). Pas de capture distante, pas d'authentification, pas de requête réseau par le script. L'ordre du manifeste est celui du montage. Aucune sortie MP4 n'est créée si un élément manque ou si un hash est incorrect.

## Limitations et qualification

- Ce chemin vérifie la structure et les CRC des chunks PNG, puis décompresse de façon bornée les scanlines RGB/RGBA 8 bits non entrelacées et vérifie leur taille exacte et les filtres PNG. Les métadonnées textuelles/exif sont refusées. Il ne reconstitue pas visuellement les pixels ni n'atteste la session réelle; FFmpeg reste le décodeur image/vidéo de référence pour le bundle. Les formats PNG autres que RGB/RGBA 8 bits non entrelacés sont rejetés (fail-closed). Pour une admission STAR plus stricte, réutiliser/porter le validateur `demo/star_evidence_manifest.py` de la PR #36 et ses tests.
- Pas de génération réelle de screenshots depuis 10.79.94.202 à ce stade, aucun accès serveur vérifié.
- Pas de preuve de lien causal entre Grafana, Thruk, n8n et GLPI sans IDs de run/incident/ticket et timestamps recoupés.
- Aucun accès aux systèmes ni déploiement sur le portail. MP4 non produit tant que les captures n'ont pas été fournies.
- Avant publication : tester la vidéo localement, vérifier la confidentialité et ajouter les métadonnées d'exécution, attestation de session, identifiants corrélés et contrôle d'accès.

## Renforcement du contrôle (incrément 2026-10-27)

Contrôle strict des chunks PNG (longueur/CRC/IHDR/IDAT/IEND), refus des timestamps UTC mal formés et des URL intégrant des identifiants, refus d'écraser une sortie symlink. Tests négatifs ajoutés. Les fichiers de tests sont des fixtures structurelles et ne constituent pas des captures d'application ni un test du décodage vidéo. Exécution CI et ffmpeg à confirmer avant toute publication.

## Garde PNG supplémentaire (2026-10-27 23:43 CET)

Le validateur du chemin `evidence_video.py` refuse désormais les flux zlib tronqués, les octets compressés ajoutés après la fin du flux, les filtres de scanline invalides, les PNG entrelacés et les chunks `tEXt`/`zTXt`/`iTXt`/`eXIf`. La sortie décompressée est bornée à 32 MiB; le PNG Playwright attendu est RGB/RGBA 8 bits non entrelacé. Ces contrôles protègent le pipeline avant FFmpeg mais **ne prouvent ni authenticité de la capture ni absence de données personnelles dans les pixels** : la revue opérateur reste obligatoire.
