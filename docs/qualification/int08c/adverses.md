# C scénarios adverses — attentes, jamais mesures runtime
Chaque ligne: seules activités antérieures strictement qualifiées et lecture du point de refus autorisées; aucune activité aval, FINISH/RESOLVE ou effet externe autorisé. Pour préflight: aucune activité. Pour collecteur: GET/history seulement, aucune commande; un terminal déjà lu ne prouve pas succès. Compteurs attendus effets externes/GLPI/n8n/DGX/live = 0, scheduling aval = 0; mesures runtime UNKNOWN. Historique indiqué = preuve future attendue, pas journal réel. Etat FAILED/UNKNOWN distingue échec workflow et état Core non réconcilié.
| Cas | Frontière | Preuve attendue | Retry | Etat attendu |
|---|---|---|---|---|
|Core indisponible|start_run|ActivityTaskFailed/TimedOut|3 max puis arrêt; réponse ambiguë reconcile|FAILED/UNKNOWN|
|Twin indisponible|OBSERVE|ActivityTaskFailed|3 max lecture; pas de gate aval|FAILED/UNKNOWN|
|Critic DENY|DGX_CRITIC|BLOCKED stage résultat|aucun retry décision|BLOCKED|
|Policy DENY|POLICY|GATE_BLOCKED|aucun retry décision|BLOCKED|
|HITL absent/invalide|HITL|BLOCKED stage résultat|attente bornée puis refus; jamais approval synthétique implicite|BLOCKED|
|Worker FAIL|REMEDIATE|ActivityTaskFailed ou FAIL|3 max si transitoire, no-effect idempotent à prouver|FAILED/UNKNOWN|
|timeout Temporal|REMEDIATE|ActivityTaskTimedOut|3 max; deadline globale à définir|FAILED/UNKNOWN|
|retry/rejeu|START/REMEDIATE|attempt et original args|même clé et lecture reconcile; divergent 409|BLOCKED/UNKNOWN|
|identité divergente|POLICY/collecteur|unqualified_stage_transition_receipt / REJECT|aucun retry contradiction|FAILED/REJECT|
|receipt invalide|REMEDIATE/collecteur|RECEIPT_INVALID|aucun retry contradiction|REJECT|
|postcheck absent|VERIFY|INDEPENDENT_POSTCHECK_MISSING|aucun retry décision|BLOCKED|
|terminal étranger|collecteur|IDENTITY_MISMATCH|aucun retry contradiction|REJECT|
|terminal non monotone|collecteur|TERMINAL_CONTINUITY_MISMATCH|aucun retry contradiction|REJECT|
|seconde lecture modifiée|collecteur|TERMINAL_CHANGED|aucun retry contradiction|REJECT|
|tentative LIVE|préflight|refus avant scheduling cible; baseline bloque après START|aucun retry|BLOCKED|
|isolation non garantie|préflight|preuve manquante, aucun history attendu|aucun retry automatique|NO-GO|
