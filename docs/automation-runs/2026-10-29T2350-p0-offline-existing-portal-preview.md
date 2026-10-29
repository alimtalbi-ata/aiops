# 2026-10-29 23:5x CET — 5/5 P0: aperçu isolé du portail existant

## Livraison et anti-duplication
- Unique PR #185, branche `release/p0-acme-integrated-candidate-20261029-1100`. SHA de livraison = commit contenant ce journal, parent `0d954251612b4ee12e13e77cebab4dee2b276c59`.
- Aucun nouveau prototype HTML, endpoint, service, connecteur, workflow CI ou dépendance. Réutilise directement `portal.main:app` et `/demo-studio/business-story` existants.
- Ajout `scripts/check_demo_portal_preview.py`: mode de secours **local uniquement**, écoute sur `127.0.0.1:17777`, HTTP GET/HEAD seulement, POST/PUT/PATCH/DELETE refusés avant l'application (405), WebSocket refusé, lancement DEMO désactivé, token interne éphémère, URLs Core/Twin/Copilot dirigées vers loopback injoignable. N'utilise pas les identifiants ni les données de production. Aucun Docker, SSH, volume, DB ou fichier local modifié par le script.
- `tests/test_portal_preview_readonly.py`: 4 tests du garde read-only, isolation des variables, navigation GET, WebSocket. Exécutés localement hors Debian: **4/4 PASS** et compileall PASS. Raccordés à `quality.yml` existant; **CI du nouveau SHA: PENDING à la rédaction**.

## Recette opérateur sans toucher à la stack
Depuis un checkout isolé du SHA de release avec les dépendances `app/requirements.txt` déjà installées:
```bash
python3 scripts/check_demo_portal_preview.py --port 17777
```
Puis sur **la même machine** ouvrir `http://127.0.0.1:17777/demo-studio/business-story`. Si l'opérateur est distant, ne pas ouvrir de port public ni réutiliser les credentials de production; ce preview n'est pas le portail Debian installé.

## Limites et release gate
- L'aperçu explique les six étapes ACME mais **n'est PAS un run Core, une analyse IA attestée, un ticket GLPI connecté, un HITL réel, une preuve Evidence authentifiée, un impact Payments mesuré ou un déploiement Debian**. Étiquettes SIMULATED / UNKNOWN / PROJECTED_ONLY.
- Stable `e54c4e9a9b37e6229559a1b587c9a06b4741a8b3` inchangé; le déployeur installé copie `demo_v2.py` et son test, injecte `main.py`, mais ne transporte pas la candidate Core/Twin/Policy/Portal. Le poller disponible sur #153 bloque ces chemins non transportés. `deploy/deploy-acme-p0.py --inspect-host` reste le préflight opérateur, sans `--apply`.
- `applied.sha`, smoke Debian, ownership Compose, rollback réel, tenant RBAC et E2E métier: **NOT_TESTED**. Verdict **READY_FOR_STABLE=BLOCKED / DEMO_READY_DEBIAN=NOT_READY**. Pas de promotion ni de déploiement.
- Prochain acte unique: préflight `--inspect-host` par l'opérateur autorisé; si refus, conserver le preview isolé comme démonstration explicative et ne pas promouvoir stable.

## Correctif P0 après smoke isolé (même journée, 23:5x CET)
- Un test HTTP réel de l'aperçu depuis le paquet CI a confirmé `/demo-studio/business-story` **200**, `POST /api/demo` **405**, mais `/policy-control` dépassait 5 secondes : `POLICY_URL` n'était pas isolé et pouvait résoudre l'hôte Docker par défaut.
- Correction minimale dans le même script : `POLICY_URL=http://127.0.0.1:1` comme Core/Twin/Copilot, sans toucher à `app/portal/main.py`. Test négatif d'isolation étendu; 4/4 tests unitaires PASS localement.
- Smoke HTTP local réel après correctif (conteneur d'exécution isolé, **PAS Debian**) : **HTTP 200** sur `/demo-studio`, `/demo-studio/business-story`, `/runs`, `/timeline`, `/twin`, `/policy-control`, `/evidence` (7/7) ; **POST /api/demo` 405** observé avant correctif, garde inchangée. Aucun backend réel contacté, aucune preuve E2E, aucune écriture production.
- CI du SHA correctif : **PENDING** à la rédaction ; requalifier avant tout handoff. Le paquet CI précédent portait un SHA de merge PR distinct du SHA HEAD ; ne pas le promouvoir comme SHA source exact.
