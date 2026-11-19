# DATA02 — Proposition UX A (non normative)
Base A c858a5f191a8c96de8e169deb546f25813217d38. SIM01/SIM02 Desktop PASS selon instruction CENTRAL. Aucun changement runtime ou simulation.

## État et écarts
- contract.ts : MissionContext source/updatedAt globaux, pas de provenance par valeur. MissionEvent ne lie pas incident/run/preuve.
- operational.ts : ReadResult distingue AVAILABLE/UNKNOWN et retrieved_at; ACL toujours false; KPI source/kind mais pas de qualification individuelle ni raison null; IncidentView synthetic bool mais pas de run/preuve; CIView sans provenance; Comparison sans identité ni nature hypothétique.
- OperationalDashboard.tsx : séparation métier/technique, trous/nulls et UTC, couverture, temps évaluation distinct collecte. Incidents synthétiques filtrés en opérationnel; KPI et comparaisons sans filtre de provenance individuel. Absence de liste vs liste vide distinguée partiellement; liste vide ne prouve pas absence réelle. Historique technique disponible sans validation locale explicite du mode de chaque réponse. Ces écarts sont une revue statique, pas une anomalie runtime reproduite.

## Contrat proposé à arbitrer (projection lecture seule, pas API déployée)
Enveloppe par jeu de données et métadonnées par valeur si sources mixtes :
```ts
type Provenance = {
  origin: 'SYNTHETIC' | 'OBSERVED' | 'UNKNOWN';
  domain: 'PLATFORM_TECHNICAL' | 'BUSINESS' | 'UNKNOWN';
  source: string;
  source_sha256: string | null;
  observed_at: number | null;
  evaluated_at: number | null;
  retrieved_at: number | null;
  freshness: 'FRESH' | 'STALE' | 'UNKNOWN';
  tenant_acl_qualified: boolean;
  runtime_attested: boolean;
};
type DataView<T> = { provenance: Provenance } & (
  { state: 'AVAILABLE'; data: T; reason: null } |
  { state: 'UNKNOWN'; data: null; reason: string }
);
type EvidenceLink = {
  incident_id: string; run_id: string; source_sha256: string;
  evidence_id: string | null; receipt_sha256: string | null;
};
```
Dates epoch secondes UTC; seuils de fraîcheur déterminés par source/B, jamais déduits de retrieved_at. Aucune valeur par défaut true pour ACL/attestation. OBSERVED ne signifie pas métier qualifié. Identité et preuves liées par tuple incident/run/source; digest de reçu distinct du digest source. Aucun changement payload SIM01/SIM02. Contrat proposé additif, non exporté tant que CENTRAL n'a pas arbitré; les champs absents restent UNKNOWN. Pas de données réelles métier sans qualification serveur; refus conservé, pas de fallback synthétique. Un zéro observé reste zéro, null reste UNKNOWN. Liste vide autorisée seulement avec lecture qualifiée, sinon UNKNOWN. Valeurs périmées identifiées, pas présentées comme état courant. Comparaison hypothétique séparée des observations et sans causalité ni preuve de rétablissement.

## Dépendances et D03
B : inventaire sources métier, unité, domaine, dates sémantiques, couverture, raison UNKNOWN, politique fraîcheur, enveloppe et qualification serveur; grants vides jusqu'à arbitrage.
C : référentiels incident/run/source, evidence_id et receipt_sha256, distinction reçu synthétique/attestation réelle; contrat simulation inchangé.
CENTRAL : arbitrer schéma/version, autorisations et mapping dans Integrated, clearing au changement mode/contexte, assemblage.
A après arbitrage : composants de provenance par panneau/valeur, états UNKNOWN explicites, dates UTC et fraîcheur, drilldown identité lecture seule; aucun changement simulation.
D03 : fixtures séparées SYNTHETIC/OBSERVED/UNKNOWN; vérifier null vs zéro, liste vide vs refus, source manquante, fresh/stale/unknown, absence d'inférence de collecte depuis évaluation, cohérence tuple et digest, mismatch fail closed, suppression résultats DEMO après changement mode, aucune fuite tenant ni POST; régression SIM01/SIM02 et responsive neuf espaces.
Tests cette livraison : NOT_RUN (texte de proposition uniquement); aucun build, POST, LIVE ou déploiement.
