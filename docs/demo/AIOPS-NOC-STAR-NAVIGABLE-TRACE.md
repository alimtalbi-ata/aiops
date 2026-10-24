# AIOps — Navigation locale entre captures NOC et étapes STAR

La page `demo/noc_star_trace_page.py` associe désormais les trois captures illustratives aux étapes de démonstration STAR par des liens d'ancrage HTML (`#cue-detect`, `#cue-verify`, etc.). Chaque ligne d'événement possède un identifiant d'ancrage généré à partir de la liste canonique de neuf cues validée par `bind_synthetic_star_events`.

L'utilisateur peut cliquer sur une étape mentionnée dans le tableau des captures pour afficher la ligne de traçabilité correspondante, son identifiant d'événement et son empreinte SHA-256. Les liens ne quittent pas le document et ne contactent aucun serveur. Les tests vérifient la présence des neuf cibles, les ancres de navigation et l'absence de liens externes.

Cette navigation reste strictement **illustrative** : les fichiers PNG proviennent d'exécutions Chromium hors ligne ; les événements sont synthétiques, avec `verified_runtime_event_links=0`. Aucun déploiement ni action sur le serveur Debian ou les applications Checkmk/Thruk/GLPI/n8n/Grafana n'a été effectué.

La prochaine étape est d'ajouter un manifeste de navigation autonome et des tests navigateur réels pour valider les clics, puis de préparer une intégration en lecture seule dans le portail de démonstration.
