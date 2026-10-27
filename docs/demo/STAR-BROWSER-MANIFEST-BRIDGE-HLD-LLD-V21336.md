# STAR V2.13.36 — Passerelle Chromium → portail unique :17777 (23 octobre 2026)

**Statut : code de contrôle hors ligne ; aucune capture runtime Debian ni intégration du portail déployé n'est attestée.**

## HLD

1. Un collecteur Chromium **opt-in et lecture seule** (candidat local séparé) produit un PNG et un manifeste `star-browser-evidence/v1`. Aucun navigateur n'est lancé par la passerelle.
2. Le `run_id`, `correlation_id` et les références d'événements sont fournis **indépendamment depuis l'ingress canonique**. Ne jamais les reconstruire depuis les manifestes, l'URL ou les images.
3. `demo.star_browser_manifest_gate.verify_browser_manifests` vérifie hors ligne l'identité, le service et la vue attendus, l'état observé, la cohérence provenance/transport, les fichiers PNG (CRC/SHA-256), les doublons, les symlinks et la chronologie dans l'ordre STAR.
4. La sortie `star-capture-evidence-v1` est consommable par `demo.star_portal_storyboard.storyboard` sans exposer d'URL brute ou de secret. Les fixtures restent `simulated`. Les captures opérateur restent `integrity_checked` : **pas de preuve d'origine runtime**.
5. Revue humaine indépendante avant toute promotion ou communication métier. Aucune validation HITL ni remédiation LIVE.

## LLD, limites et rollback

- Entrées : répertoire existant non symlink, noms de manifestes JSON simples et références canoniques indépendantes. Aucun accès réseau, écriture de ticket, CMDB, workflow, conteneur ou port.
- Rejet de toute identité absente ou contradictoire, preuve malformée, PNG réutilisé, chemin traversant, capture sans fuseau, statut incohérent ou attestation d'autorité non fiable.
- **Limite :** le module ne vérifie ni la vérité des pixels, ni la page réellement visitée, ni la qualité du masquage, ni la proximité de l'horodatage avec l'événement source. Le collecteur Chromium et la revue des deep links n8n/Grafana/GLPI V1 :8080 doivent être qualifiés séparément.
- `n8n completed` ≠ validation métier ; `RUN_ID_MISSING` entre workflows V1 02/03 reste à diagnostiquer sans fabrication d'identité.
- Rollback : revert des trois fichiers du correctif sur la branche PR. **Aucune** modification de `main`, du bridge V1, du portail :17777 ou des services Debian.

## Tests et prochaine étape

```bash
python3 -m unittest discover -s tests -p 'test_star_browser_manifest_gate.py' -v
python3 -m unittest discover -s tests -p 'test_star_*.py' -q
```

Intégrer le collecteur Chromium candidat et qualifier sa CI sur le SHA exact ; ensuite, captures réelles seulement avec accès autorisé, contrôles des pages/identités/horodatages, SHA256 et anonymisation vérifiée. Les exemples synthétiques ne doivent jamais être présentés comme preuves runtime.


## Durcissement de l'ingestion locale (26 octobre 2026)


- Le contrat valide les types de l'objet canonique, des références d'événements, de la liste de fichiers et des champs `cue`, `service`, `view`, `provenance` et `captured_at` avant les recherches, comparaisons ou accès aux fichiers. Les entrées de forme invalide déclenchent un `ValueError` contrôlé au lieu d'une exception accidentelle.

- Les manifestes sont lus avec un descripteur de répertoire épinglé et une ouverture relative refusant le lien symbolique final lorsque les primitives POSIX requises existent. Le lecteur borne les octets, exige un fichier régulier, vérifie la cohérence des métadonnées avant/après lecture et rejette UTF-8 invalide, JSON non standard et clés dupliquées.

- Le bridge complet, son storyboard, son gate de replay, ses dépendances, tests et HLD/LLD sont maintenant inclus explicitement dans la liste approuvée du kit cumulatif. Le workflow du kit relance ces tests et vérifie l'archive contre le checkout épinglé.

- Limite inchangée : SHA-256 et cohérence de manifeste ne prouvent ni une session authentifiée, ni l'écran exact réellement visité, ni l'horodatage de l'événement externe. Les neuf checkpoints restent non qualifiés au runtime cible tant que les sources indépendantes et captures autorisées ne sont pas intégrées.
