# V2.13.52 — intégrité atomique du ZIP historique (descripteur stable)

## Besoin et défaut corrigé

La récupération V2.13.51 liait l'inventaire à deux SHA-256, mais `recover()` calculait le SHA de l'archive par une ouverture puis rouvrait le **chemin** pour parser le ZIP. Un renommage/remplacement du chemin entre les deux ouvertures pouvait faire analyser un autre fichier. La vérification du SHA du membre sélectionné limitait le risque de substitution de ce membre, sans garantir que le validateur global et le SHA d'archive concernaient le même objet. `inventory()` présentait la même fenêtre.

## HLD/LLD et contrat

`inventory()` / `recover()` → `_open_stable_archive(Path)` → `os.open(O_RDONLY|O_NOFOLLOW|O_NONBLOCK)` → `os.fstat()` fichier régulier → SHA-256 du **descripteur ouvert** → `seek(0)` → `zipfile.ZipFile(stream)` sur **le même descripteur** → validation globale de l'archive → inventaire ou extraction du membre explicitement épinglé en quarantaine privée `O_EXCL`.

La prévention des symlinks ne dépend plus uniquement de `Path.is_symlink()` (précontrôle sujet à course). Un remplacement du chemin après l'ouverture n'affecte plus les octets effectivement parsés. `O_NONBLOCK` évite qu'un FIFO substitué bloque le worker avant `fstat()`. Le fichier ZIP original n'est jamais modifié ; aucune ouverture de réseau, de session navigateur ou de service Debian.

**Contrat conservé** : mêmes champs `aiops-zip-source-inventory/v1`, mêmes arguments CLI et SHA-256, dry-run/inventaire par défaut, extraction seulement avec `--apply` et deux empreintes, `QUARANTINED_NOT_QUALIFIED`. La stabilité des octets n'atteste ni l'origine, ni la complétude, ni la sûreté du code. La détection des secrets reste heuristique : revue humaine obligatoire avant tout push.

## Qualification synthétique et patrimoine

- `python -m unittest discover -s tests -p 'test_zip_source_recovery.py' -v` : 23 tests locaux PASS (20 historiques + 3 nouveaux).
- Nouveaux tests : substitution du chemin pendant l'inventaire ; substitution du chemin pendant l'extraction épinglée ; symlink substitué juste avant l'ouverture malgré un précontrôle contourné.
- `python -m py_compile recovery/tools/zip_source_recovery.py tests/test_zip_source_recovery.py` : PASS local.
- Neuf archives candidates V2.13.42–51 présentes dans le contexte de reprise : inventaire lecture seule effectué, sans extraction. Il ne s'agit pas des originaux complets F20.13 ni des portails V2.13.4/6/10 ; aucun fragment n'est promu en source complète.
- La qualification GitHub CI et les tests E2E Chromium du portail : à vérifier séparément sur le commit exact.

## Réversibilité et sécurité

Rollback : revert du commit de cette évolution sur la branche de PR, sans toucher aux fichiers en quarantaine. Aucun merge vers `main`. Ne pas modifier la prod Debian, le bridge V1, les services GLPI/n8n/Grafana, la CMDB, Temporal, les tickets, les ports ou les sessions navigateur. Aucun état métier LIVE n'est validé par ces tests.
