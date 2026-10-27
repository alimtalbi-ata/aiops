# Capture Playwright opérateur — 5 applications réelles

L'adaptateur `demo/evidence_browser_capture.py` est un **portage ciblé du garde-fou de requêtes** de la PR #36 (`demo/star_browser_request_fence.py`). Il prépare les captures de **portail, Thruk, Grafana, n8n et GLPI** depuis des sessions navigateur autorisées. Aucune page réelle n'est capturée par les tests ou dans GitHub Actions.

## Plan privé (hors Git)

Préparer un JSON de la forme :

```json
{
  "schema_version": 1,
  "run_id": "RUN-001",
  "incident_id": "INC-001",
  "ticket_id": "TCK-001",
  "session_label": "operator-20261027",
  "captures": [
    {
      "service": "portal",
      "url": "https://example.invalid/portal",
      "allowed_origin": "https://example.invalid",
      "proof_selector": "#run-id",
      "proof_text": "RUN-001",
      "redact_selectors": [".sensitive"],
      "approved_get_urls": []
    }
  ]
}
```

Le tableau doit comporter **exactement cinq entrées**, avec les services `portal`, `thruk`, `grafana`, `n8n`, `glpi`, chacun avec son URL et origine **réellement revues**. L'exemple est volontairement incomplet et non exécutable comme capture. Les URL et sélecteurs ne doivent pas être devinés. `proof_text` doit être égal au run_id, incident_id ou ticket_id déclaré; le DOM doit l'afficher. L'URL de capture n'accepte pas de query/fragment, notamment pour éviter de journaliser un token; les vues qui nécessitent un query sécurisé restent BLOCKED jusqu'à adaptation revue.

Les dossiers de sortie et de sessions doivent être en mode `0700`, et les fichiers de session en `0600`; le script refuse les permissions plus larges et écrit les PNG/manifeste en `0600`.

Créer cinq fichiers de session Playwright (générés lors d'une connexion légitime) dans un répertoire privé distinct : `portal.json`, `thruk.json`, `grafana.json`, `n8n.json`, `glpi.json`. Ils contiennent potentiellement des cookies et secrets : **ne jamais les committer ni les publier comme artefacts CI**. Un stockage d'état présent n'est pas une attestation de session active.

## Utilisation

```bash
python3 demo/evidence_browser_capture.py \
  --plan /chemin/prive/plan.json \
  --output-dir /chemin/prive/captures \
  --storage-state-dir /chemin/prive/sessions
# DRY_RUN par défaut : validation seulement, zéro navigation.

# UNIQUEMENT sur poste opérateur autorisé, hors CI, après revue des URLs/masques :
AIOPS_CAPTURE_OPERATOR_APPROVED=YES python3 demo/evidence_browser_capture.py \
  --plan /chemin/prive/plan.json \
  --output-dir /chemin/prive/captures \
  --storage-state-dir /chemin/prive/sessions --capture

python3 demo/evidence_video.py \
  --manifest /chemin/prive/captures/manifest.json \
  --evidence-root /chemin/prive/captures \
  --output /chemin/prive/demo-preuves.mp4
```

Préparer le navigateur sur le poste opérateur : `python3 -m pip install playwright` et `python3 -m playwright install chromium`. Le script refuse l'option `--capture` si `CI=true` ou `AIOPS_STAR_NO_RUNTIME=1`; il exige en plus l'accord explicite `AIOPS_CAPTURE_OPERATOR_APPROVED=YES`. Les captures ne sont jamais exécutées en CI.

## Limites et sécurité

- Navigation exacte GET seulement, sous-requêtes GET autorisées **uniquement si listées par URL exacte**; POST, redirections non attendues et requêtes cross-origin bloquées. Les applications complexes peuvent échouer à charger : déclarer BLOCKED et examiner les requêtes nécessaires, ne pas désactiver le filtre. GET n'est pas intrinsèquement sans effet.
- Le script vérifie la présence du texte de corrélation et d'au moins un sélecteur de masquage par application; les masques ne garantissent **pas** l'absence d'autres secrets à l'écran. Revue humaine des cinq PNG indispensable avant toute publication.
- Chaque PNG est lié à SHA-256, URL source, horodatage UTC, run/incident/ticket et libellé de session **déclaratif**. Le manifeste reste `OPERATOR_SUPPLIED_UNATTESTED` avec `runtime_authenticated=false` et `production_qualified=false`. Les métadonnées ne prouvent ni l'authentification, ni la causalité, ni l'absence de manipulation.
- Les captures sont enregistrées dans un dossier privé existant et ne remplacent jamais des fichiers. Aucun appel au serveur Debian, aucun déploiement ni action de remédiation.
- Les tests `tests/test_evidence_browser_capture.py` sont **purement offline**, sans Chromium. Ils valident le contrat et les refus; ils ne qualifient pas les cinq interfaces réelles. L'exécution réelle Playwright/MP4 reste NOT_TESTED tant qu'un opérateur autorisé n'a pas fourni de session et de pages.
