# Bundle MP4/SRT/receipt — captures opérateur (P0)

Ce lot complète `demo/evidence_browser_capture.py` et `demo/evidence_video.py` de la PR #43. Il réutilise **ciblément** les principes STAR de la PR #36 : refus des clés JSON dupliquées dans le manifeste, contrôle de provenance et validation complète du décodage MP4 (`ffmpeg -f null -`), ainsi que `ffprobe` pour codec, résolution et durée. Il ne reprend pas le générateur de scènes **synthétiques** `demo/generate_demo_video.py`, qui demeure un chemin distinct explicitement SIMULATION.

## Entrées et confidentialité

Le dossier des captures doit contenir `portal.png`, `thruk.png`, `grafana.png`, `n8n.png`, `glpi.png` et `manifest.json` produits par l'adaptateur autorisé, ou fournis par un opérateur après revue. Les cinq entrées doivent avoir des SHA-256 vérifiés, des URLs HTTP(S) sans query/fragment, des timestamps UTC et les **mêmes** `run_id`, `incident_id`, `ticket_id`, `session_label`. Une capture manuelle sans ces identifiants est **BLOCKED** pour ce bundle. Les valeurs de corrélation sont déclaratives et ne prouvent pas la causalité ou l'identité de session.

Le répertoire de sortie doit exister avec les permissions `0700`. Les trois fichiers publiés sont `0600`. Toute collision de nom, symlink de sortie, entrée altérée, incohérence d'ID, URL à query ou échec de décodage bloque la publication. Aucun fichier existant n'est écrasé.

## Commandes (hors GitHub Actions, seulement avec des captures déjà autorisées)

```bash
mkdir -m 700 /chemin/prive/aiops-bundle
python3 -m demo.evidence_video_bundle \
  --manifest /chemin/prive/captures/manifest.json \
  --evidence-root /chemin/prive/captures \
  --output-dir /chemin/prive/aiops-bundle \
  --seconds 6
```

Sorties : `aiops-evidence.mp4` (H.264 1920×1080, cinq séquences), `aiops-evidence.srt` (sous-titres génériques sans identifiants) et `aiops-evidence.receipt.json` (SHA-256 MP4/SRT/captures, URLs et horodatages déclarés, corrélation, durée). Le manifeste final conserve `OPERATOR_SUPPLIED_UNATTESTED`, `runtime_authenticated=false` et `production_qualified=false`. Il ne doit pas être publié avant revue de confidentialité et attestation externe de session/runtime.

## Qualification

```bash
python3 -m unittest discover -s tests -p 'test_evidence_video_bundle.py' -v
```

Ce test contient un **vrai rendu et décodage ffmpeg hors ligne** à partir de PNG générés en mémoire pour la qualification technique du montage; ces PNG ne sont **pas des preuves d'applications**. Le workflow `.github/workflows/quality.yml` exécute ce test sur PR, exige `ffmpeg` et `ffprobe`, et ne contacte aucun service. L'authentification Playwright et les captures réelles de portail/Thruk/Grafana/n8n/GLPI restent **NOT_TESTED/BLOCKED** sans sessions et URLs vérifiées. Les sous-titres ne remplacent pas une narration validée.

## Prochain incrément

Contrôle strict de décodage PNG en amont de l'encodeur, manifeste Evidence Studio navigable en lecture seule, puis chaîne d'attestation de session avec vérification indépendante des cinq vues réelles. Aucun accès au Debian ni à NVIDIA NIM n'est effectué par ce lot.
