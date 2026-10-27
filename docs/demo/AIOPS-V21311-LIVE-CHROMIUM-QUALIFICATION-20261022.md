# V2.13.11 — Déploiement et Chromium en exploitation, 22 octobre 2026

Résultats rapportés depuis SRV-DEB-05 après bascule de l'unique service Compose aiops2-portal.

- `AIOPS_V21311_DEPLOY=PASS`
- Container ID : `6bdae3cf1a6e48ecc49bc4bcfd70cf41bdb34aa20c77921355adf56e6845b519`
- Active image : `sha256:ee4e3e536cdfe64d0c903f261ec5c7285b729ce08afc83dfcf3c0af578dfd95c`
- L'unique portail demeure `http://10.79.94.202:17777`.
- Chromium a ouvert `http://10.79.94.202:17777/demo/star` et rapporté 12/12 PASS : loaded, twelve_steps, initial, next, previous, direct_step, reset, pause_label, resume_label, keyboard, provenance, no_console_errors.
- Tableau d'erreurs JavaScript vide.
- Résultats conservés sur Debian : `/home/aiops/aiops-v21311-qualification/v21311-live-browser.json` et capture PNG de même nom.
- **Le test vérifie les libellés pause/reprise, pas l'écoulement réel du minuteur sur une durée complète.**
- Aucune preuve d'exécution DGX, d'accès historique approuvé ou de remédiation LIVE issue de ce test.
- Ancien contrôle V2.13.10 validait un HTTP 403 sur le replay historique. Le script de déploiement V2.13.11 contrôle à nouveau ce 403, mais un nouveau contrôle indépendant post-déploiement demeure conseillé.
- Préserver les fichiers Compose locaux, la sauvegarde de l'image précédente, et la séparation simulation/exports/real.
