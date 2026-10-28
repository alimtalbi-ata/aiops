# 2026-10-28 03:13–03:16 Europe/Paris — P0 NOC upstream TLS fence

## Base et lectures
- Départ `main`: `1ed749129e32ea9a8854c437c7de9a6a8b43e35b`, vérifié avant création de branche.
- PR #36 (NOC Livestatus/export et HMAC read model), PR ouvertes #37, #39, #41, #43, ainsi que #71 et #75 consultées; roadmap PR #39, `README.md`, `docs/PROJECT-CONTINUITY.md`, architecture et catalogue sur main lus. Pas de merge massif de #36. Le pont signé NOC déjà porté depuis #36 est conservé.
- Branche dédiée: `fix/noc-transport-tls-fence-20261028-0313`; HEAD avant journal: `7c01b6127f0a847f09348877143d7ae6c94a3546`.
- PR draft: https://github.com/alimtalbi-ata/aiops/pull/78 (non fusionnée).

## Micro-lot de code
- `app/portal/noc_runtime.py`: refuse tout `http://` non-loopback avant création du transport HTTP, même si l'URL est allowlistée. `https://` et loopback littéral `localhost`/`127.0.0.1`/`[::1]` restent autorisés.
- `tests/test_portal_noc_runtime_adapter.py`: tests négatifs remote HTTP, métadonnées cloud et faux localhost; tests de non-régression HTTPS/loopback.
- `docs/architecture/NOC-SIGNED-READMODEL-BRIDGE-20261027.md`: contrat TLS et compatibilité.
- `docs/automation-runs/2026-10-28-0313-p0-noc-transport-tls.md`: présent journal.

## Commits confirmés GitHub
- `29493a5a101da16e43b282326887ef0028bb6c21`: source.
- `f686f3dd1d5174800c56deab29530796f383a26c`: tests.
- `7c01b6127f0a847f09348877143d7ae6c94a3546`: documentation.

## Validation et preuves
- Tests locaux: **NOT_TESTED** (pas de checkout local de cette branche dans cette exécution).
- GitHub Actions `quality.yml`: PR ouverte, run non encore retourné par l'API à 03:16 Europe/Paris; **PENDING/NOT_VERIFIED**. Ne pas déclarer PASS avant vérification de la conclusion du dernier HEAD. Les tests utilisent un transport factice pour prouver le refus pré-réseau : pas de véritable Checkmk/Thruk/Grafana.
- Aucun secret de production, aucune commande LIVE, aucune action Debian, aucun merge, aucun déploiement.

## Risques et limites
- Changement volontairement incompatible avec les fournisseurs HTTP distants existants : réponse 503 fail-closed jusqu'à terminaison TLS vérifiée. Un loopback autorisé n'est pas une preuve de sécurité du service adjacent.
- Authentification de source HMAC ≠ preuve d'observation LIVE. RBAC tenant, Core ACL, métriques Grafana et diagnostic RAG/LLM réel **NOT_TESTED/BLOCKED**.
- PR #71 modifie aussi `noc_runtime.py` (contexte DEMO signé); vérifier conflits et intégrer les protections sans écraser ses changements. PR #75 renforce séparément la corrélation tenant/LIVE.

## Prochain micro-lot
1. Vérifier le run Actions du HEAD de #78; corriger les tests si nécessaire, puis mettre à jour ce journal avec URL/conclusion.
2. Intégrer proprement les protections de #71/#75 après revue, sans merge massif.
3. Qualifier Checkmk/Thruk réel en conteneurs CI et ACL tenant avant d'autoriser toute donnée observée.
