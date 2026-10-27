# AIOps — Vue de traçabilité STAR et preuves NOC hors ligne

`demo/noc_star_trace_page.py` génère une page HTML autonome pour les neuf événements STAR du démonstrateur, à partir de `demo/noc_star_event_binding.py`. Chaque étape affiche son nom, l'identifiant de l'événement et l'empreinte SHA-256 de son JSON canonique. Une seconde table identifie les trois captures NOC et les étapes qu'elles illustrent.

**Garantie de provenance :** seule une série de neuf événements `SYNTHETIC` appartenant à un même `run_id` et `incident_id` est acceptée. Les captures sont exclusivement des `OFFLINE_TEST` et les liens sont `ILLUSTRATIVE_SYNTHETIC_HASH_BINDING`, sans attestation d'exécution réelle. Une empreinte de contenu ne prouve ni l'origine de l'événement, ni son exécution sur le serveur Debian.

Le workflow Chromium exécute trois nouveaux tests `tests/test_noc_star_trace_page.py`, notamment l'affichage des neuf étapes et le refus des identités de run incohérentes. **Le résultat de la CI du dernier commit doit être vérifié avant qualification.**

**Limites :** la page ne contient pas encore de chronologie horodatée authentifiée, de collecte Checkmk/Thruk LIVE ni d'intégration au portail Debian `:17777`. Prochain développement : générer un jeu d'événements synthétiques déterministe et intégrer la page HTML au lot d'artefacts du démonstrateur après le contrôle du manifeste.
