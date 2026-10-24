# AIOps NOC — Contrôle d'admission des preuves Chromium hors ligne

Le module `demo/noc_browser_evidence_gate.py` valide les trois captures PNG produites par les tests Chromium du NOC unifié : `unified.png`, `synthetic.png` et `checkmk-export.png`. Il compare leurs empreintes SHA-256, leurs tailles et leurs structures PNG via `inspect_png` au manifeste `aiops-noc-offline-browser-artifacts-v1`.

Toute preuve prétendant être authentifiée par le runtime, autorisant une action LIVE, contenant un fichier inattendu, une capture manquante, un lien symbolique, un nom de fichier inconnu, des tailles incohérentes ou un PNG altéré est rejetée. La seule classe admise est `OFFLINE_TEST`, sans possibilité de promotion vers `LIVE`.

Le workflow `.github/workflows/star-offline-chromium-real-render.yml` teste les cas nominaux et dégradés puis applique ce contrôle au répertoire de preuves réellement généré par Chromium avant publication de l'artefact. Les captures restent celles d'un navigateur exécutant des scénarios ACME synthétiques et des exports Checkmk non authentifiés. **Aucune donnée de production Debian ni capture authentifiée Grafana/n8n/GLPI ne sont incluses.**

Prochaine étape : indexer les manifestes OFFLINE_TEST dans le centre de preuves du démonstrateur et y faire apparaître la différence entre résultat de test, observation de supervision et preuve authentifiée d'incident, sans confusion possible.
