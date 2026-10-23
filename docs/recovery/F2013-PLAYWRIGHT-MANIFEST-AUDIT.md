# F20.13 — Audit de migration des captures Playwright historiques

## Contexte et objectif
Le 15 octobre 2026, les scripts `playwright-evidence-campaign.py` et `demo-multistack-capture.py` ont produit des manifestes différents pour UCP/F20.13. Les conversations historiques contiennent des sorties de Chromium et SHA-256, mais une partie des heredocs est tronquée. Le manifeste multistack indique notamment un état PASS pour `10-grafana.png` correspondant à **/login**, donc **pas** à une vue métier authentifiée.

Ce module permet de **faire l'inventaire sans faire semblant de qualifier les captures** et évite de demander au moteur STAR actuel d'interpréter abusivement un ancien statut PASS.

## Code
- `demo/star_legacy_playwright_audit.py`: entrée JSON uniquement, pas d'accès HTTP/Chromium, sortie expurgée et non destructive.
- `tests/test_star_legacy_playwright_audit.py`: contrôles page de login Grafana, SHA déclaré mais non confirmé, noms de capture invalides, identité de navigateur manquante.
- Déclenché par le workflow `.github/workflows/star-capture-evidence.yml`.

## Exemple de consultation
```bash
python3 -m demo.star_legacy_playwright_audit /chemin/DEMO-MULTISTACK-MANIFEST.json --output /tmp/legacy-audit.json
```

Le fichier de sortie est créé exclusivement ; aucun écrasement. Le résultat ne contient ni URL ni contenu de capture, et *tous* les champs `runtime_authenticated`, `integrity_verified`, `business_state_verified` et `eligible_for_star_proof` sont toujours **false**.

## Réintégration ultérieure
1. Récupérer les fichiers PNG complets hors GitHub et vérifier SHA-256 réel + signature/CRC PNG.
2. Réexécuter une capture sur page métier authentifiée (Grafana alert/panel, n8n exécution, GLPI ticket), avec lecture seule, et vérifier les identifiants de run/cue.
3. Construire un pont explicite du manifeste historique vers `star-capture-evidence-v1`; **ne jamais convertir automatiquement PASS en preuve runtime**.
4. Examiner la CI sur le SHA exact avant de qualifier la modification.

Aucun composant Debian de production n'a été touché.
