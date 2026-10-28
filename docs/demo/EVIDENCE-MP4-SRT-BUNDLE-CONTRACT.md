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

## Incrément 2026-10-28 — épinglage des octets avant FFmpeg

Le bundle valide d'abord les PNG d'entrée, puis les copie via des descripteurs
`O_NOFOLLOW` dans un répertoire temporaire privé. Il refuse fichiers non réguliers,
taille excessive, changement détecté pendant la copie, collisions et chemins suspects.
Il **revalide les empreintes SHA-256 du manifeste sur ces copies** et passe exclusivement
ces copies à FFmpeg. Une modification du fichier source après cet épinglage ne change
donc pas les octets lus par le moteur de rendu. Aucun nouveau droit LIVE n'est accordé.

Tests : `python -m unittest discover -s tests -p 'test_evidence_snapshot.py' -v`
et la régression `test_render_uses_pinned_bytes_after_source_changes` dans
`test_evidence_video_bundle.py`. Les fixtures ne sont pas des preuves de
portail/Thruk/Grafana/n8n/GLPI. Les snapshots ne garantissent pas l'authenticité
de la session, le contenu visuel ou une protection contre un autre processus
ayant le même compte Unix et accès au répertoire privé. Le contrôle de
confidentialité opérateur et l'attestation indépendante restent bloquants.


## Incrément 2026-10-28 — audit indépendant du reçu local (PR #86)

Après la génération du bundle, une vérification indépendante des **octets locaux**
peut être effectuée sans navigateur ni réseau :

```bash
python3 -m demo.evidence_bundle_audit \
  --bundle-dir /chemin/prive/aiops-bundle \
  --capture-root /chemin/prive/captures
```

L'auditeur exige le répertoire bundle privé (0700), des fichiers réguliers
non symboliques, des noms de sortie fixes, un JSON sans clés dupliquées,
des champs de provenance strictement non attestés et cinq captures dans
l'ordre canonique. Il réutilise `demo.evidence_video.verify` pour valider
les PNG, leurs empreintes, leurs horodatages UTC et leurs origines déclarées,
puis vérifie SHA-256 du MP4 et du SRT avec détection de modification pendant
la lecture. Les échecs renvoient `BLOCKED` et le code 2.

**Frontière explicite :** `LOCAL_BYTES_VERIFIED_UNATTESTED` ne valide ni
l'authentification des sessions, ni le contenu visuel, ni les permissions
d'accès des applications, ni la causalité entre les IDs. Cet auditeur ne
décode **pas** le MP4 : le décodage FFmpeg est contrôlé séparément lors de
la génération. Un reçu et des octets modifiés ensemble ne constituent pas
une signature ou une attestation externe. Les tests de cet auditeur utilisent
des PNG techniques et un faux MP4 pour les cas de hashes ; un test distinct
assemble aussi un **vrai MP4 hors ligne avec FFmpeg**, puis le fait auditer.
Aucun de ces fichiers n'est une capture authentifiée d'application, ni une
preuve de session ou d'incident réel. Aucun chemin
LIVE n'est ouvert.


## Incrément 2026-10-28 — SRT canonique et durée des scènes (PR #91)

L'auditeur vérifie désormais **le contenu** du SRT en plus de son empreinte :
les cinq sous-titres doivent être exactement ceux générés par
`demo.evidence_video_bundle.subtitles` (libellés non sensibles et ordre
portal/Thruk/Grafana/n8n/GLPI). Une modification du texte accompagnée d'un
SHA-256 recalculé est **BLOCKED**. La durée déclarée doit être finie,
correspondre à cinq scènes de 2 à 20 secondes entières et respecter une
tolérance de 0,25 s sur le MP4 complet. Les tests couvrent l'injection de
texte, le rehash, les durées non finies et incohérentes, ainsi que le bundle
FFmpeg réel hors ligne.

Cette validation est **une cohérence déclarative** du reçu/SRT, non une
analyse de la bande vidéo ni une attestation de session. L'auditeur ne décode
toujours pas le MP4 et n'établit ni la réalité des cinq vues ni leur
confidentialité visuelle. Les PNG techniques de CI ne sont pas des captures
opérateur authentifiées.


## Incrément 2026-10-28 — liaison service/fichier et URL sans secrets (PR draft)

Le vérificateur partagé `demo.evidence_video.verify` exige désormais le nom
canonique `<service>.png` pour chaque service : un reçu ne peut pas déclarer
`thruk.png` comme preuve du portail, même si les octets et le SHA-256
correspondent. Les URL sources déclarées refusent query string, fragment,
identifiants, espaces, anti-slash, chemins `..`, ports invalides et origines
non canoniques. Ce contrôle s'applique à la validation, au montage et à
l'auditeur indépendant, y compris lorsque le reçu a été réécrit.

Les tests négatifs sont `test_evidence_video.py` et
`test_evidence_bundle_audit.py`, exécutés via `quality.yml`.
**Ce contrôle est structurel** : un opérateur malveillant peut encore fournir
une image visuellement falsifiée ou recopier les mêmes pixels sous plusieurs
noms. Les URL et identifiants restent déclaratifs, sans attestation de session,
revue visuelle des masques, ni qualification LIVE. Les fixtures de CI ne sont
pas des captures authentifiées.
