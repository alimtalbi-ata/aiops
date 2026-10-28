# P0 NOC — prévisualisation hors ligne Checkmk/Livestatus

Date : 2026-10-28. PR : [#83](https://github.com/alimtalbi-ata/aiops/pull/83).

## Portage ciblé

Source examinée : PR #36 `demo/noc_checkmk_export.py` (blob `3ffc90055912e68a66a99193037cbf2cbfb01638`), `demo/noc_livestatus_import.py` (blob `c81dde43da0e5e1dbaf64932e9961e0254bb9aa6`), tests `test_noc_checkmk_export.py` et `test_noc_livestatus_import.py`. Repris : schéma `aiops-checkmk-host-export-v1`, états 0/1/2/3, bornage temporel, refus de colonnes inconnues, doublons et états booléens. Non repris : sortie brute des hôtes et `plugin_output` (risque de divulgation tenant).

## API

`POST /api/noc/checkmk-export/preview` accepte exclusivement un export JSON opérateur hors ligne avec `schema`, `source=CHECKMK_EXPORT`, `read_only=true`, `live_remediation_authorized=false`, `captured_at` UTC et `hosts` (nom, état entier, output). Jeton `AIOPS_PORTAL_READ_TOKEN` obligatoire. Corps limité à 64 KiB, 1–500 hôtes, âge déclaré de 0–300 secondes. JSON strict (doublons et NaN interdits). Réponse : agrégats d'états uniquement, `UNVERIFIED_OFFLINE_EXPORT`, `OPERATOR_EXPORT_UNVERIFIED`, aucune identité, texte plugin ou preuve runtime.

La page NOC propose un exemple **SYNTHETIC DEMO ONLY** et une prévisualisation. Elle ne se connecte pas à Checkmk/Thruk et ne stocke pas les exports. Les identifiants tenant/org/workspace non reconnus sont rejetés ; il ne s'agit **pas** d'un RBAC multitenant. Ne jamais coller un export contenant des secrets. L'opérateur contrôle la date déclarée : la fraîcheur ne constitue pas une preuve d'authenticité.

## Qualification et risques

Tests unitaires/API négatifs dans `tests/test_noc_checkmk_offline_preview.py` ; step ajouté au `quality.yml` existant. Les tests sont contractuels, pas une intégration de vrais services. Checkmk/Thruk conteneur, Grafana métriques, Core ACL, NIM/NGX et Debian : **NOT_TESTED/BLOCKED**. La classification DEMO de l'exemple UI ne doit jamais être promue en observation réelle. Aucun réseau externe, aucune écriture Core, aucune action LIVE.

Rollback : revert des commits de la PR, retirer le routeur et le panneau NOC. Aucune migration ou donnée persistée.

Prochain micro-lot : tester un vrai Checkmk en conteneur CI isolé, authentifier le fournisseur d'export, puis lier les identifiants tenant et Run via Core avant tout drilldown nominatif.
