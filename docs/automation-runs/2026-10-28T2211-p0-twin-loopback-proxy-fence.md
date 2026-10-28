# 2026-10-28 22:11 CET — ACME Twin: qualification loopback sans proxy ambiant

## État lu avant modification
- `main` HEAD vérifié : `ec05c89e92a6611922dccbe3690ce1476e3aec92` ; base de travail `#157` HEAD `4f049eb9d35f7d92e8993e56d7dbca69dc8123e7`. Vérification répétée avant écriture du journal.
- PR #142 (parcours inversé) et #148 (arêtes SQL sourcées) ouvertes/draft, `mergeable=true`, checks de leurs HEAD exacts [#40744150243](https://github.com/alimtalbi-ata/aiops/actions/runs/40744150243) et [#40760838278](https://github.com/alimtalbi-ata/aiops/actions/runs/40760838278) `completed/success` ; #157 `completed/success` [#40768112890](https://github.com/alimtalbi-ata/aiops/actions/runs/40768112890). Pas de fusion implicite.
- Autres créneaux consultés : #140, #141 (fermée), #143, #144, #145, #146 (non mergeable), #153, #156 (préflight couverture déployeur). Les branches de livraison Twin et le journal précédent `2026-10-28T2158-p0-twin-readonly-qualification.md` ont été lus. #156 est CI `completed/success` sur `8aea522787d72f67100d26a695c7120c6cddf207`, sans preuve Debian.

## Une livraison verticale
- [PR draft #159](https://github.com/alimtalbi-ata/aiops/pull/159), branche `feat/p0-twin-acme-loopback-proxy-fence-20261028-2211` basée exclusivement sur #157, sans modifier les autres branches.
- Commit code/tests/docs : `a461e57fb1ad97f571f92a43314513b2a1b6f2d2`.
- Fichiers : `scripts/qualify_acme_twin_readonly.py`, `tests/test_twin_impact_real_integration.py`, `docs/demo/ACME-TWIN-READONLY-QUALIFICATION-V1.md`, présent journal.
- Le qualificateur rejette désormais les URL loopback non canoniques (caractères de contrôle, blancs, port avec zéro initial), contourne explicitement les variables `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY` pour empêcher l'envoi du bearer à un proxy, et exige les en-têtes `Cache-Control: no-store` / `WWW-Authenticate: Bearer` pour le refus anonyme HTTP 401.
- Test d'intégration supplémentaire contre **vrai Twin Docker et PostgreSQL 16 éphémères** avec proxies invalides et `NO_PROXY` vide, plus cas négatifs d'URL. Pas de nouveau workflow ; `.github/workflows/quality.yml` réutilisé.
- Contrat serveur `GET /api/twin/impact/{node_id}` inchangé ; contrat de sortie `aiops.acme-twin-readonly-qualification.v1` inchangé, `contract_status=PASS` ne prouve que le seed, `overall=NO_GO` reste obligatoire.

## CI, preuves et risques
- [quality.yml run #40770081635](https://github.com/alimtalbi-ata/aiops/actions/runs/40770081635) sur commit code `a461e57fb1ad97f571f92a43314513b2a1b6f2d2` : **completed/success**, 3 jobs SUCCESS (policy/static, Core/PostgreSQL + Twin Docker/PostgreSQL, Grafana réel). Ce résultat a été vérifié via GitHub, pas extrapolé.
- Le HEAD final **après commit du présent journal** doit être requalifié sur sa propre CI ; ne pas annoncer PASS tant que ce nouveau run n'est pas `completed/success`. Son lien et résultat seront transmis dans la PR #159.
- Tests locaux : `NOT_TESTED` ; CI Twin éphémère : `PASS` sur SHA ci-dessus ; Debian : `NOT_TESTED`.
- Source topologique : `db/migrations/005_seed_acme.sql`, arêtes E08/E06/E04/E02/E01, parcours SAN-A→stockage→VM→application→Payments. Aucune arête SAN→hôte, aucune panne Payments ni basculement SAN-B attestés.
- **READY_FOR_STABLE=BLOCKED / GO=NO-GO** : ACL tenant, CMDB/runtime, E2E Core→IA→Policy SIMULATE→Evidence→Studio, compatibilité déployeur Twin, rollback et `applied.sha` Debian non qualifiés. La branche `deploy/aiops2-stable` n'a pas été touchée. Le lot 5/5 Recette est seul propriétaire de la promotion.
- Aucun SSH, aucune action LIVE, aucune migration ni déploiement.

## Prochain micro-lot
- Transmettre au lot 5/5 Recette les SHAs de #142→#148→#157→#159 et la couverture déployeur #156. Ne proposer une candidate stable qu'après contrôle du transport du module Twin, du rollback, des ACL tenant et d'une recette terrain horodatée.
