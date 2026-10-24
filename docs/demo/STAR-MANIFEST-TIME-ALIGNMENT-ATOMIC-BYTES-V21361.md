# V2.13.61 — Alignement temporel STAR lié aux octets vérifiés

## Problème reproduit
Le contrôle d'alignement temporel relisait les manifestes après le contrôle des identités, PNG et SHA-256. Un fichier remplacé entre ces deux lectures pouvait fournir un autre `captured_at` valide mais **non contrôlé**. La comparaison de timestamps ne prouvait alors plus que les données analysées étaient celles validées par le premier contrôle.

## Correction fonctionnelle
- `verify_browser_manifests(..., include_manifest_digests=True)` calcule le SHA-256 des **mêmes octets** que ceux analysés en JSON, en plus des contrôles PNG existants.
- `verify_event_capture_alignment` relit les manifestes dans un tampon d'octets unique et exige l'égalité avec le digest renvoyé par le contrôle d'intégrité. Toute substitution intermédiaire provoque `ValueError` (fail-closed).
- Par défaut, les réponses du bridge ne changent pas. L'empreinte `capture_set_sha256` déjà retenue par les replays n'inclut pas ce champ auxiliaire : la compatibilité des pins existants est préservée.
- Les vérifications de provenance, identité canonique, temps de capture, PNG et source d'événement sont réutilisées, sans duplication de l'implémentation F20.13.

## Chaîne de confiance HLD
Source d'événement déclarée indépendante → identités canoniques → manifeste Chromium et PNG (SHA-256) → digest des octets de manifeste effectivement analysés → seconde lecture contrôlée → fenêtre de temps événement/capture. Les preuves restent `CONSISTENT_UNAUTHENTICATED` et ne prouvent ni session applicative, ni authenticité runtime, ni validation métier, ni approbation HITL.

## LLD et tests
`include_manifest_digests` est un booléen strict, désactivé par défaut. `manifest_sha256` n'est retourné que sur demande dans les entrées concernées. Le nouveau test adversarial modifie le timestamp entre les deux lectures : avant correction la modification aurait pu passer, après correction elle est rejetée. Tests supplémentaires : digest exact, mode invalide, digest global des neuf captures inchangé, alignement inchangé en absence de substitution.

Qualification CI : `STAR event-to-capture time alignment (offline)`, `STAR browser manifest bridge (offline)`, `STAR event-source byte binding (offline)`, et Quality Gates généraux. Tous les essais restent synthétiques, isolés et sans réseau runtime.

## Limites et patrimoine
Ce correctif ne récupère pas les sources Playwright F20.13 originales. Les chemins et hypothèses documentés dans `docs/recovery/F2013-SOURCE-LOCATION-MAP-20261015-V21360.md` restent des pistes, pas des fichiers récupérés. Les scripts historiques complets doivent être inventoriés et vérifiés par SHA-256 avant réutilisation. Un attaquant capable de modifier les fichiers après la fin du contrôle exige une conservation immuable et un ancrage indépendant : le présent correctif sécurise les lectures de l'audit, pas le stockage de preuves à long terme.

## Rollback
Revert des commits touchant `demo/star_browser_manifest_gate.py`, `demo/star_event_capture_alignment.py`, leurs tests et cette note, uniquement sur la branche de PR draft. Aucun déploiement, port, écriture GLPI/n8n/Grafana/DB, conteneur ou remédiation LIVE.
