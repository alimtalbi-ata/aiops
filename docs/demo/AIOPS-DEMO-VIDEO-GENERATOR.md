# AIOps — génération de la vidéo complète de démonstration

## Objectif
Générer un film MP4 présentable de 72 secondes, sous-titré, à partir d'un parcours STAR de neuf scènes : détection, corrélation, CMDB/contexte, analyse IA/critique, ticket, HITL/Policy, remédiation simulée, vérification et bilan des preuves.

## Prérequis
- Python 3.10+
- Playwright Python et Chromium installés
- ffmpeg disponible dans PATH
- `espeak-ng` ou `espeak` facultatif pour la narration française. Sans moteur vocal, la vidéo est tout de même générée avec sous-titres.

## Installation (dans une copie de travail)
```bash
python -m pip install playwright
python -m playwright install chromium
# Installer ffmpeg et, si souhaité, espeak-ng avec le gestionnaire de paquets du système.
```

## Génération
```bash
python -m demo.generate_demo_video --scenario SAN_FABRIC_P1 --out dist/aiops-demo-video
```
Pour Payments : `--scenario PAYMENTS_P2`. Pour forcer le mode sans voix : `--no-voice`.

Le répertoire de sortie doit être neuf : le générateur refuse d'écraser des fichiers existants. Résultats :
- `AIOps-Demo-Complete.mp4` — vidéo H.264, 1920×1080, 25 fps
- `AIOps-Demo-Complete.srt` — sous-titres français
- `AIOps-Demo-Complete.manifest.json` — manifeste de provenance

## Contrôles et limites
Le script ne contacte aucun endpoint AIOps, Grafana, n8n, GLPI ou DGX. Il construit une démonstration synthétique complète, et non un enregistrement du runtime actuellement déployé. Les écrans sont des scènes de présentation illustrées, pas des captures des interfaces réelles. Le manifeste maintient explicitement `runtime_authenticated=false`, `dgx_independently_attested=false`, `live_execution_qualified=false` et `live_action_authorized=false`.

La qualification du script est distincte de la qualification E2E du portail. Ne pas déclarer une démonstration runtime qualifiée à partir du seul MP4.

## Génération automatisée GitHub Actions

Le workflow `.github/workflows/generate-demo-video.yml` génère aussi le MP4 et publie les trois fichiers comme artefact téléchargeable. Il se déclenche sur les changements du générateur/tests/documents sur la branche de travail, ou manuellement via **Actions → Build complete AIOps demo video → Run workflow**. Choisir `SAN_FABRIC_P1` ou `PAYMENTS_P2`, puis télécharger l'artefact de l'exécution terminée. Le workflow contrôle que le MP4 dure environ 72 secondes et que le manifeste ne revendique aucune attestation runtime ou action LIVE.

La publication d'un artefact GitHub Actions n'installe pas la vidéo dans le portail Debian. Aucun déploiement n'est réalisé par ce workflow.


## Demo Center du portail existant

La route `/demo/` du portail affiche un contrôle de génération vidéo, un choix de scénario (SAN P1 ou Payments P2), un état de progression et les liens de récupération du MP4, du SRT et du manifeste. Elle n'ouvre aucun port ni serveur supplémentaire.

La fonction de lancement est **désactivée par défaut**. Pour l'autoriser explicitement dans l'environnement du processus portail, définir :

```bash
AIOPS_DEMO_VIDEO_ENABLED=true
```

Ce paramètre n'est pas appliqué automatiquement par le code et ne constitue pas une instruction de déploiement. Avant de l'activer sur une instance partagée, vérifier la politique locale de contrôle des ressources, les dépendances du générateur et l'accès à `dist/demo-video-runs`. Le lancement est limité à un processus à la fois et à deux scénarios prédéfinis ; les chemins de sortie sont générés par le serveur. Les téléchargements ne sont exposés qu'après la validation du manifeste.

Routes ajoutées au routeur du portail :
- `POST /demo/video` — lancement opt-in, JSON `{"scenario":"SAN_FABRIC_P1"}` ou `{"scenario":"PAYMENTS_P2"}`.
- `GET /demo/video/{job_id}` — état du rendu.
- `GET /demo/video/{job_id}/artifact/video` — MP4.
- `GET /demo/video/{job_id}/artifact/subtitles` — sous-titres.
- `GET /demo/video/{job_id}/artifact/manifest` — manifeste de provenance.

Le suivi d'état est conservé en mémoire du processus portail : après un redémarrage ou si plusieurs workers sont utilisés, un identifiant de tâche précédent peut ne plus être connu. Le test automatisé vérifie les contrats de route, le désactivé par défaut, la liste blanche des scénarios, l'absence de commande arbitraire et la création de répertoires uniques. Il ne remplace pas un test HTTP de bout en bout ni un rendu réel dans l'environnement Debian.

Le portail ne prétend pas que cette vidéo est une capture de l'interface déployée : elle reste une vidéo narrative synthétique. L'activation ne doit pas être assimilée à une qualification runtime ou DGX.
