# STAR — vérification locale des captures applicatives

**État : implémentation du vérificateur hors ligne ; aucune capture runtime fournie ni qualifiée.**

## Usage

Le vérificateur `demo/star_evidence_manifest.py` lit un manifeste JSON opérateur et les PNG indiqués. Il n'ouvre aucune URL, ne lance aucun navigateur, ne contacte aucun backend et n'écrit pas dans les applications. Les origines doivent être explicitement autorisées sur la ligne de commande.

```bash
python demo/star_evidence_manifest.py \
  --manifest ./star-manifest.json \
  --evidence-root ./capture-bundle \
  --allowed-origin https://grafana.example.invalid \
  --allowed-origin https://n8n.example.invalid \
  --allowed-origin https://glpi.example.invalid \
  --output ./star-audit-report.json
```

L'exemple utilise des domaines réservés à la documentation : remplacez-les par les origines réellement autorisées de votre environnement. Le fichier de rapport doit être nouveau ; le vérificateur refuse d'écraser un fichier existant. Les chemins des captures sont relatifs à `--evidence-root`, par exemple `evidence/detect.png`.

## Contrat du manifeste

Le manifeste a `schema_version: 1`, `provenance: OPERATOR_SUPPLIED_SCREENSHOTS_UNATTESTED` et une liste `captures`. Chaque entrée décrit un cue de `demo/star_snapshot_choreography.py` avec `cue`, `service`, `view`, `source_url`, `captured_at_utc`, `run_id`, `incident_id`, `screenshot_path` et `screenshot_sha256`. `ticket_id` est facultatif. Les neuf cues attendus sont contrôlés ; les absences, doublons, origines non allowlistées, chemins dangereux, PNG malformés et sommes divergentes ne passent pas.

## Signification du résultat

- `BYTES_VERIFIED_UNATTESTED` : les CRC sont cohérents, le flux zlib des pixels se décompresse vers la taille de scanline attendue, les codes de filtre sont valides, les dimensions restent bornées et le SHA-256 correspond au manifeste. Le vérificateur accepte un sous-ensemble explicite de PNG non entrelacés ; il ne reconstitue ni n'affiche les pixels.
- `MISSING` ou `REJECTED` : preuve absente ou non vérifiée ; aucune réussite implicite.
- `complete_byte_set=true` signifie seulement que les neuf fichiers et métadonnées satisfont ce contrôle local.

Le vérificateur force à `false` les attestations d'identité applicative, d'événement runtime, d'état métier, d'approbation humaine, d'autorisation LIVE et de qualification production. Un opérateur peut fournir une image d'une page de connexion ou d'un ancien écran : son hash ne démontre pas que l'écran correspond au run, ticket ou événement revendiqué. Une vérification indépendante des identifiants applicatifs et de la fenêtre temporelle reste obligatoire avant toute qualification STAR.

## Tests

`tests/test_star_evidence_manifest.py` construit neuf images PNG synthétiques et teste l'intégrité octet, la couverture des cues, le hash incorrect, les origines refusées, la traversée de chemin, les liens symboliques, les CRC corrompus, les flux zlib invalides malgré un CRC/hash cohérent, les filtres de scanline invalides, les doublons et l'impossibilité de promouvoir des champs d'attestation fournis par l'opérateur. Ce sont des tests unitaires isolés, pas une capture Chromium ni une validation des applications réelles.
