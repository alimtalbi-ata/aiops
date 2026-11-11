# 2026-10-28 23:50 Europe/Paris — Recette 5/5, cohérence applied.sha locale

## Point de départ et revue des autres lots
- HEAD `main` vérifié avant les modifications : `13c455256f34e5e0f0ac55146326888b0fb84c42` (#160).
- HEAD `deploy/aiops2-stable` : `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` ; comparaison GitHub **diverged** (main 40 ahead / 633 behind stable). Branche stable protégée, cinq checks obligatoires ; aucune promotion fast-forward possible depuis main.
- Branche de travail exclusive #156 `fix/p0-stable-deploy-coverage-20261028-2149`, SHA initial `0173c0fa0e655194fce7abb779a88dbb6095c7b4`. Pas de modification des branches des autres créneaux.
- PR #153 : HEAD `34c4364176b0dd33784162a117072d9abdc6e96b`, CI PR [#40776502679](https://github.com/alimtalbi-ata/aiops/actions/runs/40776502679) SUCCESS sur ce SHA ; correctif de nom Docker #164 fusionné **dans #153 uniquement**. Déployeur inspecté : il copie `demo_v2.py`, `test_demo_v2.py` et injecte un bloc dans `portal/main.py`, **ne transporte pas** Core/Twin/Copilot.
- PR #140/#142/#143/#145/#146 consultées : #140/#145 UI empilées ; #142 Twin ouverte ; #143 V2 ouverte ; #146 non fusionnable. #141 fusionnée, #144 fermée après portage #160. #165 Twin rapporte [CI verte](https://github.com/alimtalbi-ata/aiops/actions/runs/40777607084) sur vrai Twin/PostgreSQL éphémères ; #166 UI et #167 Ledger ont leurs workflows globaux **en échec** (Policy/Temporal), malgré leurs tests ciblés. Pas d'assemblage sûr.
- `docs/PROJECT-CONTINUITY.md`, journal #153 du rollback, scripts du déployeur, `scripts/check_demo_stable_coverage.py`, `scripts/check_demo_field_readonly.py`, tests et `.github/workflows/quality.yml` consultés.

## Une micro-livraison verticale
Dans la PR draft [#156](https://github.com/alimtalbi-ata/aiops/pull/156), la sonde de terrain existante peut maintenant comparer **en lecture seule** un SHA approuvé de 40 caractères hexadécimaux avec un fichier local `applied.sha` explicitement désigné par l'opérateur. Sans ce couple de paramètres, le contrôle reste `NOT_TESTED`.

- `scripts/check_demo_field_readonly.py` : options `--expected-sha` et `--applied-sha-file` ; lecture bornée à 42 octets, fichier régulier uniquement, refus du lien symbolique final, des tailles inattendues, SHA invalides et changements de métadonnées pendant la lecture. Un mismatch ou un fichier illisible **bloque avant tout HTTP** ; jamais de contenu ou chemin local dans le reçu. La sonde réseau demeure GET loopback sans proxy/redirection.
- `tests/test_demo_field_readonly.py` : six tests négatifs/de non-régression supplémentaires et un chemin CLI positif sur serveurs HTTP fixtures éphémères. **Ces fixtures ne sont pas Core/Twin/Copilot/Portal réels.**
- Contrat additif `aiops.demo-field-readonly-preflight.v1` : `applied_sha_verified=MATCH_UNATTESTED|BLOCKED|NOT_TESTED`, `checks.local_applied_sha_consistency=PASS|BLOCKED` si comparaison demandée. **MATCH_UNATTESTED ne prouve ni provenance du fichier, ni exécution du cron, ni intégrité d'une machine.** `overall=NO_GO` reste constant. Aucune route API modifiée, aucune donnée LIVE.
- Commits : `cfdba193ac4024a9a0dbe0c6b953882a7b8f2107` (code), `833fc97d41a2fa8cece87e0506b66b8ee7f96152` (tests), `dd0599e549d8279a4346d0b3c5251ae6e5bddf43` (horodatage refus), `d6d188bf540a7a05f4d39133a4c32585d461d4dc` (test CLI positif).

## Recette opérateur proposée, **non exécutée sur Debian**
Après approbation d'un SHA et transfert contrôlé, l'opérateur exécute localement et séparément du poller, avec quatre ports loopback explicitement autorisés :

```sh
python scripts/check_demo_field_readonly.py \
  --core-url "http://127.0.0.1:<CORE_PORT>" \
  --twin-url "http://127.0.0.1:<TWIN_PORT>" \
  --copilot-url "http://127.0.0.1:<COPILOT_PORT>" \
  --portal-url "http://127.0.0.1:<PORTAL_PORT>" \
  --expected-sha "<SHA40_APPROUVE>" \
  --applied-sha-file "/chemin/absolu/vers/applied.sha"
```

Ce n'est pas une instruction à exécuter automatiquement sur SRV-DEB-05. Le fichier est fourni par l'opérateur ; **son existence, son emplacement, son origine et son authenticité ne sont pas vérifiés ici**. Conserver ensuite hors secrets le JSON horodaté, l'identité de l'opérateur et les logs signés, plus les smoke-tests RBAC/tenant, Policy SIMULATE, Evidence et rollback. Le simple poller Git ne valide rien de cela.

## Validation et limites
- Tests locaux dans cet environnement : **NOT_TESTED** (pas de checkout GitHub accessible au conteneur ; aucune exécution prétendue).
- GitHub Actions `quality.yml` : lancé automatiquement par push/PR ; résultat du HEAD code `d6d188bf540a7a05f4d39133a4c32585d461d4dc` **à confirmer après achèvement**. Aucun PASS annoncé avant lecture des résultats.
- Tests sur Debian, `applied.sha` authentique, Docker rollback réel, auth/RBAC tenant, chaîne Core→Temporal→Analyst/Critic→Policy→Evidence→Portal, impact Payments, corrélation run/incident/evidence, confidentialité des captures : **NOT_TESTED**.
- Risque : un `applied.sha` local falsifié peut correspondre au SHA attendu. Cette comparaison n'est **pas** une preuve cryptographique indépendante ; un GO requiert une attestation opérateur et des tests terrain observés.

## Matrice de décision et prochain lot
| Critère | État |
| --- | --- |
| Lecture bornée et refus local applied.sha | CI en cours, NOT_TESTED terrain |
| `main` vers stable fast-forward | BLOCKED (historiques divergents) |
| Transport effectif Core/Twin/Copilot | BLOCKED (déployeur #153 portail uniquement) |
| Policy/Temporal, tenant RBAC, E2E ACME | NOT_TESTED / CI empilées rouges |
| Rollback et smoke-tests Debian authentifiés | NOT_TESTED |
| Promotion `deploy/aiops2-stable` | **NO-GO / READY_FOR_STABLE=BLOCKED** |

**Prochain micro-lot :** vérifier la CI du HEAD final, coordonner avec #153 un transport explicite et réversible des composants retenus, puis assembler une PR candidate unique et faire exécuter une recette terrain authentifiée par un opérateur autorisé. Ne pas promouvoir ni déployer sur cette seule comparaison.

## Confirmation GitHub Actions (ajoutée après achèvement)
- **HEAD code + journal `a4611596779f2194a3c51e57d071f31efea42198`** : [quality.yml PR #40783323415](https://github.com/alimtalbi-ata/aiops/actions/runs/40783323415) **completed/success** et [quality.yml push #40783313587](https://github.com/alimtalbi-ata/aiops/actions/runs/40783313587) **completed/success**. Trois jobs SUCCESS chacun ; logs du job `policy-and-static` de la PR lus : **16 tests de la sonde fixture/lecture SHA exécutés, OK**. Jobs Core/PostgreSQL et Grafana réels CI SUCCESS, sans qualifier l'E2E ACME.
- Ce complément documentaire constitue un nouveau commit ; vérifier séparément ses checks sur son SHA exact avant toute fusion. La décision **NO-GO** reste inchangée.
