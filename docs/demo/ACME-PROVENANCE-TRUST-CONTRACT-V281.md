# ACME — provenance et qualification du raisonnement (V2.8.1)

Date: 2026-10-22. Portée : développement GitHub uniquement, aucun déploiement.

## Contrat de démonstration

1. Un registre Analyst/Critic persisté dans Core atteste uniquement l'enregistrement d'un objet. Le nom de modèle enregistré est une **déclaration**, pas une preuve cryptographique ou indépendante d'inférence DGX.
2. Chaque `supporting_evidence_id` doit être recoupé avec le registre Evidence du run. Distinguer `ABSENT`, `MARQUEUR D'ÉTAPE`, `SYNTHETIC` et `ORIGINE INCONNUE`. La présence d'un identifiant ne démontre pas la causalité.
3. `validated` absent doit s'afficher `INCONNU`, jamais `REFUSÉ` ou `VALIDÉ` par défaut. `validated=true` reste une déclaration Critic, pas une approbation humaine.
4. Une décision Policy enregistrée ne prouve pas le fencing au dernier point d'effet. L'absence de reçu d'effet dans un export ne prouve pas l'absence de toute action.
5. `/policy-story` = narration/simulation. `RUN-A4449145A6E377FF` = historique, à examiner avec ses preuves. `RUN-56C124FC8F7A0490` = `INTELLIGENCE_UNAVAILABLE`, échec et non réussite DGX.
6. Les données du scénario client sont SYNTHETIC tant qu'une source authentifiée ne les qualifie pas autrement. Pas de bouton d'approbation réelle, de changement Policy ni de remédiation LIVE.

## Tests exigés

Cas sans Critic, modèle seulement déclaré, preuves absentes, stage markers, preuve synthétique, provenance inconnue, HTML non fiable, contradiction Policy, état inconnu. Les tests locaux ne constituent pas une qualification du portail déployé.

## Gel du 22 octobre

Aucun build, redémarrage, déploiement, migration, modification de conteneur/configuration/base, ni action LIVE jusqu'à la fin de la démonstration. Après la démo, staging isolé et autorisation explicite avant tout déploiement.
