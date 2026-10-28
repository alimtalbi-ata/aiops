# Golden DEMO ACME — frontière d'écriture et liaison au fixture (2026-10-28)

**Statut : code proposé, qualification Core/Temporal/GLPI réelle NOT_TESTED.**

Le portail public présentait auparavant `POST /api/demo` sans authentification. Cette route écrit un Incident et un Run dans Core et demande l'exécution de ce Run. Le nouveau garde-fou exige **un jeton DEMO dédié** (`AIOPS_PORTAL_DEMO_TOKEN`, ASCII, au moins 32 caractères), distinct de `AIOPS_INTERNAL_TOKEN`. S'il est absent, la route renvoie 503 **avant toute écriture** ; si l'identité est invalide, 401. Le jeton est saisi dans la page du portail et effacé de l'input immédiatement, sans stockage local, URL ou rendu dans la réponse. Le jeton interne Core n'est jamais demandé à l'utilisateur.

Génération opérateur, à conserver uniquement dans le fichier d'environnement local protégé, jamais dans Git :

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(36))'
```

La variable est passée au conteneur du portail via Compose et n'a pas de valeur par défaut. L'endpoint est **désactivé tant que l'opérateur n'a pas configuré un jeton distinct**. Les autres endpoints de démonstration synthétique en lecture seule ne changent pas. `tests/synthetic-e2e.sh` requiert désormais le jeton dans son environnement et le transmet à curl via stdin plutôt que la ligne de commande. Ne pas lancer ce test contre le serveur Debian sans autorisation explicite.

## Liaison des identifiants

- Fixture validé par `acme_impact_read_model` : `ACME-DEMO-SAN-001` (SAN P1), `ACME-DEMO-PAY-002` (Payments P2), SHA-256 exact des octets.
- Core : création DEMO `external_id=ACME-DEMO-SAN-001`, avec `incident_id=INC-ACME-DEMO-SAN-001` **retourné et vérifié**. Le préfixe `INC-` est la convention Core ; il ne transforme pas le fixture en événement réel.
- Scenario Core : `SCN-GOLDEN-PAYMENT-P1` **déjà présent** dans `db/migrations/005_seed_acme.sql`. Il emploie les CI du jumeau canonique `ACME-*`, différentes des CI du fixture `SAN-FABRIC-A`. Aucune équivalence CMDB vérifiée n'est revendiquée.
- Idempotency key `DEMO-ACME-SAN-PAY-<sha256[:16]>`, distincte de l'ancienne `DEMO-GOLDEN-PAYMENT`. Le Run retourné doit avoir `mode=DEMO` et un ID `RUN-*` valide avant de demander l'exécution.
- Réponse `execute` : l'ID doit correspondre au Run créé. Même après acceptation, `runtime_attested=false`, `ticket_id=null`, `production_qualified=false`, `live_remediation_authorized=false`. Aucun ticket GLPI, checkpoint ou capture authentifiée n'est revendiqué.

**Tests contractuels hors ligne** : auth absente/invalide, jeton identique au Core, divergence d'Incident, mode LIVE renvoyé, reçu d'exécution divergent, fixture contaminé, non-divulgation d'erreur, API du portail et déterminisme. Le workflow `.github/workflows/quality.yml` existant les exécute en PR. Cela ne prouve ni la présence d'un vrai GLPI éphémère ni la visibilité d'un Run en E2E.

**Risque / rollback** : la démonstration est désactivée par défaut (fail-closed). En cas de besoin, revenir au commit antérieur via PR contrôlée ; ne pas supprimer la protection sans remplacer la frontière d'écriture. La PR #37 (script E2E) modifie le même fichier et devra réconcilier l'en-tête Authorization lors du rebase. La PR #77 (topologie) modifie `app/portal/main.py` et devra réconcilier le montage de routes. Aucun merge massif ni action LIVE.
