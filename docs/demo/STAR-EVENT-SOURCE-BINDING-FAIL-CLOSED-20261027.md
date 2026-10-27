# STAR — liaison des sources d'événements, captures et identité (27 octobre 2026)

## Besoin métier

Chaque checkpoint STAR doit être rapproché d'un événement identifié et du même run_id, correlation_id et event_ref que la capture. La somme SHA-256 relie les octets effectivement lus au digest déclaré ; elle n'authentifie ni l'origine de l'événement ni le serveur, l'utilisateur ou l'application qui l'aurait produit.

## Implémentation et interfaces

- Module : demo/star_event_source_binding.py.
- API : verify_event_source_binding(root, expected, manifest_names, anchors, source_files).
- Entrée par checkpoint : manifeste de capture, ancre temporelle et fichier JSON local dans events/. Le fichier source est limité à 65 536 octets ; son SHA-256 doit correspondre à source_sha256 dans l'ancre. Les clés dupliquées, références/états incohérents, sources partagées entre checkpoints, chemins non canoniques et JSON mal formés sont refusés.
- Chaîne de validation : star_event_source_binding → star_event_capture_alignment → pont de manifeste/navigateur, contrôle d'identité, chorégraphie allowlistée et intégrité structurelle PNG. Toutes les dépendances sont locales au dépôt ; aucun service externe n'est appelé.
- Le lecteur ouvre root, events/ et le fichier via des descripteurs de répertoire. Il exige O_NOFOLLOW, O_DIRECTORY et la prise en charge de dir_fd, contrôle les types de fichiers et les tailles, puis compare les métadonnées du descripteur avant/après lecture. Une primitive nécessaire manquante ou un chemin symbolique entraîne un échec fermé.

## Vérification et packaging

Le vérificateur du ZIP borne le nombre de membres à la somme exacte des entrées de métadonnées et de la liste de sources approuvées ; l'ajout d'une source ne laisse donc pas un seuil statique obsolète faire échouer la qualification.

Les tests tests/test_star_event_source_binding.py utilisent exclusivement des PNG et événements synthétiques dans des répertoires temporaires. Ils couvrent cohérence SHA, identité, état, heure, service, clés JSON dupliquées, symlinks, fichiers surdimensionnés et absence de primitives système requises. Le workflow .github/workflows/star-event-source-binding-offline.yml exécute la suite hors ligne. La source, le test, le workflow et cette fiche sont embarqués explicitement dans le kit cumulatif ; le test du kit vérifie l'égalité exacte des octets avec le checkout épinglé.

## Provenance historique et limites

Cette évolution se base sur les registres docs/recovery/HISTORICAL-CODE-REGISTRY-20261023.md et docs/recovery/OCTOBER-2026-ARCHIVE-CONTEXT-AND-REUSE.md. Il ne s'agit pas d'une récupération complète du kit original F20.13 Playwright. Les ZIP historiques ne sont pas copiés dans Git ; les fragments de terminal tronqués, sessions de navigateur, captures non anonymisées, exports privés et secrets ne sont pas importés.

Les résultats restent UNAUTHENTICATED : une somme correcte ne prouve pas que l'événement vient réellement de Grafana, n8n ou GLPI. L'authentification réelle, la provenance indépendante, la décision HITL, l'issue métier, l'E2E Debian :17777 et toute autorisation LIVE restent non qualifiés. Aucune écriture de service ni opération de production n'est réalisée.

## Rollback

Le changement est limité à la branche de PR : revert du commit pour revenir à l'ancien lecteur et au kit précédent. Aucune modification, redémarrage ou bascule runtime n'est associée à ce changement.
