# AIOps — Centre de preuves NOC hors ligne

Le composant `demo/noc_evidence_center.py` présente les manifestes d'indexation des captures Chromium dans une page HTML statique, sans API réseau ni privilège de modification. L'affichage comprend le nom de chaque capture, sa classe `OFFLINE_TEST`, son empreinte SHA-256 et sa taille en octets.

**Contrat de sécurité :** exactement trois fichiers (`unified.png`, `synthetic.png`, `checkmk-export.png`), classement `OFFLINE_TEST=3`, `OBSERVATION=0`, `RUNTIME_EVIDENCE=0`. Un manifeste annonçant une preuve de production, une promotion runtime ou des chemins inattendus est rejeté. L'affichage est indépendant du portail Debian, des collecteurs Checkmk/Thruk réels et des applications Grafana/n8n/GLPI.

Le workflow `.github/workflows/star-offline-chromium-real-render.yml` construit la page `evidence-center.html` après vérification des PNG et de `evidence-index.json`. L'artefact GitHub `noc-offline-browser-evidence` contient les trois captures et les documents de contrôle. Les tests `tests/test_noc_evidence_center.py` vérifient le rendu et les refus des revendications trompeuses.

**Qualification :** confirmer la réussite de la CI du SHA courant avant de déclarer la production de l'artefact. Les sorties Chromium restent des **captures réelles de tests hors ligne**, et ne prouvent pas le fonctionnement du serveur Debian.
