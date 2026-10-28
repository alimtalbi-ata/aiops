# Contrat P0 — sonde Core/Policy DEMO read-only v1

## Portée et limites

`scripts/probe_demo_policy_readonly.py` vérifie **uniquement** la lecture authentifiée de `GET /api/noc/runs/{run_id}/policy-status` sur un Core déjà accessible en **loopback HTTP**. Cette route est issue de la PR #144, renforcée par #147. La sonde est livrée par PR #155, empilée sur ces PR ; elle n'est pas dans `main` ni sur `deploy/aiops2-stable`.

Préconditions : exécution locale **explicitement autorisée** par l'opérateur, Core démarré sur `127.0.0.1`, identité de service interne `AIOPS_INTERNAL_TOKEN` injectée par un mécanisme hors dépôt, et paire canonique `run_id`/`incident_id` obtenue de Core. Le script n'accède jamais à un hôte distant, refuse les redirections et proxies, n'envoie que GET, n'écrit aucune donnée et n'affiche jamais le token ni la réponse HTTP brute.

Exemple **à exécuter par un opérateur autorisé, pas depuis ChatGPT** :

```bash
python3 scripts/probe_demo_policy_readonly.py \
  --base-url http://127.0.0.1:1810 \
  --run-id '<RUN_ID_CANONIQUE_DEMO>' \
  --incident-id '<INCIDENT_ID_CANONIQUE_DEMO>'
```

Le script lit `AIOPS_INTERNAL_TOKEN` dans l'environnement ; ne pas l'inclure dans les arguments ni les journaux. La sortie JSON est bornée, sans donnée d'incident. La date `observed_at_utc` provient de l'horloge **locale de la sonde**, non d'une attestation serveur.

## Résultat et refus

Schéma de sortie `aiops.demo-policy-readonly-probe.v1` : `overall=NO_GO` dans tous les cas. Si Core répond avec le contrat exact, `observation_status=CORE_READ_OBSERVED_NOT_E2E` et la paire canonique est reproduite. Une erreur rend `observation_status=BLOCKED`, code fixe sans fuite et code de sortie 2.

La sonde refuse : hôte autre que `127.0.0.1`, HTTPS, chemin ou credentials dans l'URL, identifiants malformés, bearer absent, réponse 401/503/redirection, réponse sans `no-store`, payload supérieur à 16 KiB, provenance non synthétique, identité discordante, mode LIVE, gate `PASS/ALLOW`, état inconnu, drapeaux d'attestation `true` et explication incompatible. Elle ne peut pas certifier l'authentification tenant d'un viewer à partir du bearer de service.

- `BLOCKED/MISSING` : aucune gate enregistrée, cause du blocage inconnue.
- `RESOLVED/PASS/SIMULATE` : décision persistée, **aucune** preuve de remédiation LIVE.
- `RUNNING/MISSING` : absence de terminaison attestée, aucun timeout inféré.

## Qualification et passage de relais

`quality.yml` exécute la suite `tests/test_core_demo_policy_real_integration.py` sur Core HTTP + PostgreSQL 16 éphémères. Les nouveaux tests appellent la sonde sur ce vrai service et testent les rejets ; **aucun** HITL/Temporal/Policy HTTP réel, postchecks, rollback, tenant RBAC ou Evidence E2E n'est couvert. Ne pas présenter ce test comme intégration inter-services.

La recette terrain demandée doit rester séparée du poller Debian : Core, Twin, Copilot, Portal, AI Ledger/Evidence, identité tenant, même `run_id`/`incident_id`, provenance et disponibilité sont **NOT_TESTED** par cette sonde seule. Le lot 5/5 Recette doit assembler ces contrôles, vérifier le script de déploiement (qui ne copie pas automatiquement ce nouveau module), la sauvegarde/rollback et le `applied.sha` réel avant toute promotion. Ne pas modifier directement `deploy/aiops2-stable` ; statut **BLOCKED / NO_GO**.

Les sept Runs Debian (5 BLOCKED, 1 RESOLVED, 1 RUNNING) sont des observations **rapportées par l'utilisateur**, pas revalidées ici. Aucun impact Payments observé ni preuve LIVE.
