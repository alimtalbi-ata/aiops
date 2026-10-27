# V2.13.51 — récupération historique par empreintes verrouillées

## Contexte et besoin métier

La récupération de sources depuis des ZIP cumulatifs ne doit jamais extraire un fichier différent de celui inventorié et relu. L'outil V2.13.50 contrôlait les chemins lors de l'inventaire, mais l'extraction `recover()` ne contrôlait pas **l'ensemble** des membres ZIP et n'exigeait aucune empreinte préalablement revue. Une archive modifiée entre la revue et l'extraction pouvait être acceptée ; un autre membre dangereux pouvait être ignoré.

## Architecture et contrat de sécurité

`inventory()` et `recover()` utilisent désormais le **même validateur global** : chemins POSIX, collisions insensibles à la casse, membres réguliers, plafonds de taille et compression. `recover()` exige deux SHA-256 minuscules issus de l'inventaire original (`archive_sha256` et `member_sha256`). Le moindre écart refuse l'extraction avant création du fichier. Les signatures attestent l'identité des octets **et non** la confiance dans leur provenance, leur complétude ou leur innocuité. Le filtrage des secrets reste heuristique, sans garantie exhaustive.

Interfaces : `recover(archive, member, destination, *, expected_archive_sha256, expected_member_sha256)` et CLI `--apply --allow --quarantine --expected-archive-sha256 --expected-member-sha256`. **Rupture intentionnelle** : tout appel programmatique sans pins échoue, pour éviter une restauration non liée à la revue. Le chemin de destination doit être une quarantaine privée existante ; aucun réseau ni port, aucun accès aux services de production.

```bash
python -m recovery.tools.zip_source_recovery /private/source.zip --output /private/inventory.json
# Relever les SHA-256 dans l'inventaire, comparer avec les archives originales, puis seulement :
python -m recovery.tools.zip_source_recovery /private/source.zip --apply \
  --allow 'tools/replay.py' --quarantine /private/quarantine \
  --expected-archive-sha256 '<64-hex-de-l-inventaire>' \
  --expected-member-sha256 '<64-hex-de-l-inventaire>'
```

## Qualification et limites

Tests synthétiques : archive changée après inventaire, empreinte membre erronée, absence de pins, collision de noms, traversée dans un membre non sélectionné, membre tiers surdimensionné, CLI. Le résultat `QUARANTINED_NOT_QUALIFIED` ne valide pas les dépendances, les interfaces ni le comportement E2E. Les archives originales F20.13 et V2.13.4/6/10 doivent être rapprochées séparément de leurs inventaires, sans promouvoir de fragments incomplets. Rollback : restaurer les trois fichiers modifiés ; ne jamais supprimer automatiquement les quarantaines opérateur. Aucune modification Debian ni remédiation LIVE.
