# F20.13 — Exécution du contrôle de récupération PNG

## Usage

```bash
python3 -m demo.star_legacy_png_verify /chemin/PLAYWRIGHT-EVIDENCE-MANIFEST.json --root /chemin/vers/evidence-playwright --output /tmp/legacy-png-report.json
```

Le programme contrôle la structure et le CRC des fichiers PNG présents, recalcule leur SHA-256, compare les empreintes déclarées et crée un rapport **sans écrasement**. Il ne contacte pas GLPI, n8n, Grafana ni le portail.

## Contexte

Les deux conventions historiques F20.13 (`results` pour la campagne SPA et `captures` pour la campagne multistack) sont acceptées. L'outil conserve les erreurs (`FAIL`), refuse les liens symboliques, les fichiers répétés et les PNG invalides. Les URL et les chemins de captures historiques ne sont pas exportés dans le rapport : seul le nom logique et le statut de qualification y figurent.

## Interprétation

`integrity_verified=true` signifie uniquement que les **octets PNG** correspondent à une déclaration historique valide. Cela ne prouve pas une session authentifiée, le contenu métier, la concordance avec un run STAR ou une remédiation. Les champs `runtime_authenticated`, `business_state_verified`, `eligible_for_star_proof` restent `false`.

Un test CLI supplémentaire contrôle la création du rapport, l'absence d'URL sensible et le refus d'écrasement. La qualification CI doit être consultée sur le dernier SHA avant de déclarer le cycle validé.
