# AIOps V2.12.9 — qualification de traçabilité historique hors ligne

V2.12.9 vérifie les références analyste, critique et événements dans l'export de preuves, l'identité commune du run, la déclaration DEMO/BLOCKED, les états de décision BLOCKED, la provenance déclarée et l'intégrité SHA-256 du kit.

## Exécution Debian

```bash
cd /home/aiops/aiops-v28-demo
python3 -m unittest discover -s tests -p 'test_qualify_historical_trace_v2129.py' -v
python3 tools/qualify_historical_trace_v2129.py \
  --run /tmp/aiops-dgx-history/run.json \
  --ledger /tmp/aiops-dgx-history/ai-ledger.json \
  --evidence /tmp/aiops-dgx-history/evidence.json \
  --kit /tmp/acme-evidence-center-v2127/kit \
  --report /tmp/aiops-v2129-trace-report.json
```

## Limites
Le contrôle est borné au run historique `RUN-A4449145A6E377FF`, fixé par le module V2.12.5. Il ne certifie ni l'origine indépendante des données, ni l'exécution DGX, ni le blocage réel de l'exécuteur, ni une remédiation LIVE. Les décisions sont contrôlées **comme déclarations enregistrées**, pas comme observation du moteur d'exécution. Ne pas importer les exports historiques en production.

## Prochaines qualifications
Les interactions Chromium V2.12.7 et les contrôles d'intégrité V2.12.8 restent indépendants. Pour qualifier le fencing de l'exécuteur, fournir un test d'intégration dédié, isolé, non destructif, instrumentant explicitement la tentative et son refus.

Aucune modification requise des fichiers Docker Compose locaux ou de la politique de production.
