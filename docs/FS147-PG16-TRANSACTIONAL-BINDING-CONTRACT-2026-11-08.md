# FS147 — contrat transactionnel PG16 pour liaison et rejeu (proposition, non déployée)

Statut : CODE seulement. Aucun DDL exécuté, aucune migration appliquée, aucune lecture GLPI/Temporal attestée. À confronter au schéma réel avant intégration.

## Identité et invariants

Portée unique : mode DEMO, ticket GLPI **147 déjà existant**. Une requête LIVE ou visant un autre ticket est DENIED avant toute écriture. Identité de liaison immuable : `(tenant_id, alert_fingerprint, incident_id, run_id, evidence_id, glpi_ticket_id, mode)`. Les cinq identifiants sont non vides, NFC et exempts de caractères de contrôle. `fs147_binding_key.derive_fs147_key` produit une clé versionnée, mais **pas** une garantie d'unicité. Une même alerte ne doit pas produire silencieusement plusieurs incidents ou runs : distinguer explicitement clé de déduplication d'alerte, clé de lancement et clé de liaison complète.

## Contraintes SQL proposées (à adapter au schéma réel)

```sql
-- Illustration uniquement ; NE PAS exécuter sans migration revue.
CREATE TABLE fs147_binding (
  binding_key text PRIMARY KEY,
  tenant_id text NOT NULL,
  alert_fingerprint text NOT NULL,
  incident_id text NOT NULL,
  run_id text NOT NULL,
  evidence_id text NOT NULL,
  glpi_ticket_id integer NOT NULL CHECK (glpi_ticket_id = 147),
  mode text NOT NULL CHECK (mode = 'DEMO'),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, run_id, evidence_id),
  UNIQUE (tenant_id, alert_fingerprint, incident_id, run_id, evidence_id)
);
-- Un index distinct sur la déduplication d'alerte doit dépendre du contrat
-- de cardinalité métier validé ; ne PAS imposer ici UNIQUE(alert_fingerprint).
```

## Algorithme transactionnel d'admission

1. Authentifier tenant et provenance, refuser LIVE/ticket !=147, puis vérifier le contrat de lancement (idempotency token, origine et permissions). Une lecture GLPI absente ou non authentifiée donne UNKNOWN ; aucun `POST /Ticket`.
2. Dériver la clé, ouvrir une transaction PG16, faire `INSERT ... ON CONFLICT DO NOTHING RETURNING ...` ; si conflit, relire la ligne **dans la même transaction** et comparer chaque champ et la clé. Divergence = CONFLICT ; absence/erreur/timeout = UNKNOWN. Ne jamais convertir un conflit en nouveau ticket.
3. Vérifier l'ownership courant et un epoch de fencing monotone avec `UPDATE ... WHERE owner_id=:owner AND epoch=:expected AND lease_expires_at>now() RETURNING ...`. Zéro ligne = UNKNOWN/CONFLICT, jamais succès. Un simple timestamp client n'est pas un fencing.
4. Stocker la décision Policy avec provenance ; DENY/STOP_AUTO = DENIED, PENDING = NEEDS_HUMAN. Pour HITL, relire la validation native authentifiée liée **à ticket 147, run, action, chemin, taille/empreinte, demandeur, validateur distinct et expiration**. Une validation historique du ticket 146 ne vaut jamais approbation.
5. Préparer l'outbox avec clé unique `(tenant_id, run_id, action_id, intent_version)` et état READY dans la transaction ; commit. Aucun signal Temporal dans la transaction. Un worker ne peut dispatcher qu'après nouveau contrôle de fencing/Policy/HITL.
6. Après crash, `DISPATCHING`, `DELIVERED`, ACK absent, état Temporal non autoritatif ou réponse perdue = UNKNOWN et réconciliation lecture seule. Ne jamais réémettre aveuglément un signal ; n'admettre la reprise qu'après preuve Temporal WAITING_FOR_HUMAN, outbox READY, absence d'effet antérieur et revalidation transactionnelle. Une approbation ciblée valide ne constitue pas à elle seule un feu vert.

## Matrice d'acceptation

| Entrée | Sortie maximale |
|---|---|
| DEMO, 147, liaison identique, lecture autoritative | SAME_BINDING (observation seulement) |
| LIVE, ticket 146, Policy DENY, HITL REJECTED | DENIED |
| HITL PENDING, informations humaines manquantes | NEEDS_HUMAN |
| GLPI inaccessible, fencing inconnu, Temporal incertain, outbox ambiguë | UNKNOWN |
| Clé égale mais payload différent, ou identité de run/evidence divergente | CONFLICT |
| Toutes les preuves positives | ELIGIBLE_FOR_REVALIDATION, **jamais exécution automatique** |

## Propriété des interfaces et blocages

- **Core** : contrat, identité et transaction PG16, preuve de rejeu.
- **Intégration** : lecture GLPI 147 existant et validation native authentifiée ; jamais création de ticket.
- **Worker** : ownership, epoch fencing, outbox et non-répétition des effets.
- **Twin** : observations lab `df/du/ls` uniquement, provenance et UNKNOWN sur manque.
- **Portal** : affichage des états réels, aucun faux RESOLVED ; routes FS1113 inchangées.

Qualification manquante : migration PG16 et tests de concurrence/restart, refus Policy/HITL natif, réconciliation Temporal, CI exacte, empreintes d'images Debian et gate candidat fs1097. Production `aiops2-portal:fs1073-csp-candidate` intouchée. Aucun déploiement ni effet LIVE autorisé.
