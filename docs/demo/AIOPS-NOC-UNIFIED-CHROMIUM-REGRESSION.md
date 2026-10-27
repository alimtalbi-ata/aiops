# AIOps NOC unifié — correction du rendu et qualification Chromium

Le workflow NOC/RAG du commit `187aaa4` a échoué : le générateur `demo/noc_unified_offline.py` produisait deux attributs d'iframe contenant le texte littéral `+left+` et `+right+` au lieu du HTML des tableaux de bord. Ce défaut empêchait l'affichage réel des vues intégrées bien que leur modèle ait été validé.

**Correction :** insertion de deux contenus HTML échappés dans les attributs `srcdoc` des iframes sandboxées (`allow-scripts`, jamais `allow-same-origin`). Deux assertions de non-régression vérifient que les chaînes de substitution ne subsistent pas et que les informations ACME Payments et FC port figurent bien dans le HTML généré.

**Qualification navigateur :** `tests/test_noc_unified_chromium.py` lance le vrai navigateur Chromium dans GitHub Actions, bloque les requêtes réseau et vérifie que chaque iframe affiche son panneau métier respectif. Le workflow `.github/workflows/star-offline-chromium-real-render.yml` a été étendu à ce test. Son résultat doit être confirmé sur le commit correspondant.

**Périmètre :** pages synthétiques et exports hors ligne non authentifiés uniquement. Aucun navigateur n'accède à Checkmk, Thruk, Grafana, GLPI, n8n ou au portail Debian `:17777`, et aucune capture de ce test n'est une preuve de fonctionnement de la production.
