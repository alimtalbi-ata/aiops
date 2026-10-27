# STAR — Validation du nom des captures Chromium

Le rendu de fixtures `demo/star_offline_chromium_fixture.py` construit les noms des PNG à partir du champ `cue` fourni dans un manifeste. Ce champ était auparavant accepté sans vérification explicite contre la liste officielle, ce qui rendait le nom de sortie contrôlable par une entrée non fiable.

Désormais, avant toute création de fichier, le moteur exige que chaque scène figure exactement dans `demo.star_snapshot_choreography.CUE_BY_NAME` et que les noms soient uniques dans la campagne. Un cue inconnu ou répété est refusé. Deux tests ciblés ont été ajoutés à `tests/test_star_offline_chromium_fixture.py`. Le workflow `STAR screenshot integrity collector` exécute déjà cette suite.

Cela reste une qualification de pages HTML synthétiques isolées, et non une preuve authentifiée GLPI/n8n/Grafana ni un test du portail Debian `:17777`. Les PNG issus de cette campagne demeurent identifiés comme `SYNTHETIC_LOCAL_FIXTURE`, avec `runtime_proof_count=0` et sans remédiation LIVE.
