# AIOps — Qualification navigateur réelle des liens de chronologie STAR

`tests/test_noc_star_navigation_chromium.py` ouvre dans Chromium une page STAR construite à partir des neuf événements synthétiques déterministes et de l'index de trois captures `OFFLINE_TEST`. Le test clique réellement sur les liens des étapes `detect`, `analyze` et `verify`, puis vérifie `location.hash` et l'existence de la cible correspondante. Il surveille les requêtes et impose zéro accès réseau externe.

Le workflow `.github/workflows/star-offline-chromium-real-render.yml` lance désormais ce test à la suite de la construction et de l'intégrité des artefacts hors ligne. Le résultat de cette version ne peut être qualifié qu'après contrôle de la CI du commit courant.

**Portée :** Chromium vérifie l'interaction dans une page créée en mémoire. Aucune preuve ne concerne des incidents runtime authentifiés ou le fonctionnement des conteneurs Checkmk/Thruk, GLPI, n8n, Grafana et du portail Debian `:17777`. Les données restent simulées et sans commande LIVE.
