# V2.13.14 — Chronologie illustrée de l'incident SAN

## Fonctionnalité
Une frise discrète Signal → Analyst → Critic → Policy → Humain complète les 12 scènes STAR. Son état varie avec chaque scène, sans encombrer le message principal. Pour la scène 7, le risque est montré avant la décision; pour la scène 8, STOP_AUTO illustre un refus. Pour la scène 9, la revue humaine est présentée sans laisser croire à une autorisation effective.

## Provenance et exactitude
Toutes les scènes de la frise portent sur une simulation `SIMULATED_TARGET` et ne sont pas issues d'un appel DGX, d'une CMDB validée ou d'un workflow Policy LIVE. Le portail historique Core demeure distinct, non exposé sans autorisation.

## Tests livrés
`tests/browser/qualify_v21314_star.py` contrôle 12 scènes, les transitions de frise, les avertissements Analyst/STOP_AUTO, un seul jalon actif, les illustrations SVG et le viewport mobile. Ne pas annoncer de PASS avant exécution dans Chromium. Conserver aussi les tests V2.13.13 (15 checks) et V2.13.12 (13 checks) comme anti-régression.

## Procédure
Extraire l'asset et le test depuis la PR #36 via FETCH_HEAD dans une copie dédiée V2.13.14. Exécuter Playwright sur le fichier local, puis test des versions antérieures sur le même fichier. Construire image Docker candidate isolée. Déployer uniquement aiops2-portal après PASS, sauvegarde de l'image précédente et plan rollback. Vérifier HTTP 200 pour /demo/star et 403 pour le replay historique, puis exécuter Chromium sur la route servie en 17777.

## Sécurité et limites
Le port utilisateur 17777 est le seul. Aucun second portail, aucune action LIVE, aucun secret, aucun assouplissement CSP et aucun merge automatique. Les animations restent réduites si l'utilisateur a activé prefers-reduced-motion. Le code de V2.13.14 est publié mais n'est pas encore exécuté sur Debian.
