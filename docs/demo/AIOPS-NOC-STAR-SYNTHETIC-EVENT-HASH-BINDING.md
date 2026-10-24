# NOC AIOps — Liaison de neuf événements STAR synthétiques aux captures illustratives

Le module `demo/noc_star_event_binding.py` prend neuf événements de démonstration STAR dans l'ordre canonique (`detect`, `correlate`, `enrich`, `analyze`, `ticket`, `approve`, `simulate`, `verify`, `close`) et un index de captures NOC classées `OFFLINE_TEST`.

Pour chaque événement, il exige `source_type=SYNTHETIC`, un même couple `run_id`/`incident_id`, des `event_id` distincts et des identifiants bornés. Il produit une empreinte SHA-256 du contenu JSON canonique de chaque événement. Il associe les identifiants des événements aux captures uniquement selon la correspondance **illustrative** déjà documentée.

Le résultat `aiops-noc-synthetic-star-hash-link-v1` contient les neuf empreintes, trois associations de captures et les champs obligatoires `runtime_authenticated=false`, `verified_runtime_event_links=0`, `live_remediation_authorized=false`. Une empreinte du payload ne constitue pas une signature d'origine et ne prouve pas que l'événement a eu lieu dans la stack réelle.

Quatre tests vérifient le parcours nominal, le refus de runs/incidents mélangés, le refus d'une source prétendument réelle et le refus de l'ordre STAR erroné. Le workflow Chromium exécute ces tests ; le résultat du nouveau commit reste à qualifier.

**Suite :** distinguer un manifeste de simulation contrôlé d'une véritable chaîne d'identité événement→preuve attestée, puis relier le centre de preuves au portail de démo sans déployer sur le Debian existant.
