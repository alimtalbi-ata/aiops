# AIOps V2.13.55 — Preuve DOM visible après anonymisation (HLD/LLD)

**Statut : développement de branche PR, tests Chromium sur HTML synthétique uniquement ; aucune capture runtime ni attestation métier.**

## Patrimoine / origine vérifiable

Référence source : dépôt `alimtalbi-ata/aiops`, PR draft #36, branche `feat/v21310-star-portal-continuity-20261022`, avant modification au commit `dc367f6f3581faa3aa6bc82761e7623376f694f1`. Le composant `demo/star_snapshot_browser.py` avait pour Git blob SHA `a81ed0de6160dae553ead385480e9d7fc835abd4`, SHA-256 des octets `f2030c23d2a2adf4bd14c15af14a4e3491ccc5512819c1bd6efddeb4a256650f`. Une copie identique par Git blob SHA existe dans le lot historique offline `AIOps-V21346-Historical-Replay-Recovery-Cumulative-Offline-20261023.zip` (SHA-256 archive `bc6f8e11018602d6ec752c3fdad5c0e149ca9cab186f4054c368816f8ede5bc3`). Le contrôle porte sur **ce fichier complet**, pas sur un fragment de conversation. Le script Playwright F20.13 original reste indisponible ; aucune restauration F20.13 n'est revendiquée.

## Besoin métier et défaut corrigé

ACME STAR doit présenter au checkpoint exact une capture où le `run_id`, `correlation_id`, identifiant d'exécution/ticket/dashboard et l'état observé demeurent contrôlables. Le collecteur refusait déjà les identités erronées et imposait au moins un masque de confidentialité, mais un masque CSS pouvait recouvrir un conteneur parent des quatre preuves, donnant une image intègre SHA-256 dont les éléments de justification étaient masqués. Une capture ainsi produite ne peut pas être utilisée comme pièce visuelle probante.

## HLD : composants et frontières

`CapturePlan` (origine/identité/état déclarés indépendamment) → `validate_plan` (sélecteurs distincts) → `capture` (Chromium isolé, lecture seule, vérification DOM) → contrôle de recouvrement **masque / élément de preuve** → capture PNG anonymisée → manifeste SHA-256. Le contrôle de recouvrement a lieu **avant** toute écriture d'artefact. Les gardes existants de provenance, réseau et identité sont conservés. Les neuf checkpoints `detect/correlate/enrich/analyze/ticket/approve/simulate/verify/close` réutilisent le même collecteur ; aucun port ni serveur n'est ajouté.

## LLD : contrat et fail-closed

- Les sélecteurs `identity_selector`, `correlation_selector`, `event_selector`, `state_selector` doivent être distincts ; aucun sélecteur `redact_selectors` ne peut être égal à l'un d'eux.
- Dans le DOM Chromium effectivement affiché, pour chaque masque, `Element.contains(proof)` est évalué sur **tous** les éléments correspondant au masque et aux sélecteurs de preuve. Un masque ancêtre (`body`, `html`, `#proof`) est rejeté.
- Tout rejet interrompt la capture **avant** la création du PNG et du manifeste. Les masques disjoints fonctionnent normalement. Ce contrôle n'atteste ni l'authenticité de la page ni l'exhaustivité de l'anonymisation : les masques doivent toujours être revus par un opérateur avant toute diffusion.
- L'environnement CI impose `AIOPS_STAR_NO_RUNTIME=1`, `fixture_html` et `page.set_content`, sans HTTP. Le navigateur ne peut ni consulter la production Debian ni déclencher une action.

## Qualification et limites

Tests dédiés : collision directe avec les quatre sélecteurs de preuve, ambiguïté entre sélecteurs de preuve, recouvrement DOM par ancêtre, capture synthétique valide. Régression : tests Chromium existants, plan builder et request fence. La qualification E2E du portail unique `:17777`, les deep links applicatifs et les captures authentiques GLPI V1 `:8080`, n8n `:5678`, Grafana `:3000` restent **non vérifiés**. SHA-256 = intégrité des octets, pas preuve d'origine ni validation HITL.

## Rollback

Restaurer `demo/star_snapshot_browser.py` depuis le Git blob `a81ed0de6160dae553ead385480e9d7fc835abd4` dans la **branche de PR uniquement**, puis supprimer `tests/test_star_browser_mask_proof_gate.py` et cette note et retirer le test ajouté au workflow. Aucune modification de `main`, service, port, conteneur, base, ticket ou CMDB n'est nécessaire.
