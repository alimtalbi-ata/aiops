# ACME — Runbook de démonstration V2.11.4 (22 octobre 2026)

## Statut et règles
- Les tests précédemment rapportés : Policy consolidé 33/33, contrôle final 4/4, scénario Policy 3/3 ; préflight HTTP 7/7 ; navigateur Chromium 10/10, reset PASS, zéro écriture HTTP dans ce parcours.
- Ces résultats ont été obtenus séparément le 21 octobre 2026. Ils ne sont pas une nouvelle campagne globale.
- Le portail est accessible sur http://10.79.94.202:17777 ; disponibilité à revérifier juste avant la présentation.
- **Gel de démonstration** : aucune reconstruction Docker, aucun changement de politique, aucune réinitialisation SQLite, aucun démarrage d'exécuteur LIVE.
- Toutes les actions du scénario Freeze Button sont fictives. Ce scénario ne prouve ni approbation réelle ni intégration aux exécuteurs.

## Vérification pré-démo — lecture seule
Depuis /home/aiops/aiops-v28-demo :
```bash
python3 tools/acme_demo_ui_preflight_v2111.py --portal http://10.79.94.202:17777 --output /tmp/acme-demo-ui-preflight.json
/tmp/aiops-browser-qa/bin/python tools/acme_browser_preflight_v2113.py --url http://10.79.94.202:17777/policy-story
```
Les deux commandes doivent se terminer avec PASS. En cas de défaillance, ne pas annoncer que le test a réussi, conserver les traces et utiliser la présentation de secours.

## Déroulement conseillé
1. **Contexte métier** : /acme-stories. Présenter les six histoires et préciser qu'il s'agit de scénarios de démonstration.
2. **Investigation IA historique** : /timeline?run_id=RUN-A4449145A6E377FF. Montrer les éléments effectivement présents : analyse, objections Critic, décisions et sources. Ne pas prêter à ce run des résultats non affichés.
3. **Contrôle d'autonomie** : /policy-story. Faire dix clics ; illustrer le freeze de fin de mois, l'attente d'approbation, STOP_AUTO et le refus de l'ancienne réservation. Recommencer pour montrer que la session est rejouable.
4. **Qualification** : /qualification-lab. Distinguer résultats d'évaluation synthétique des mesures d'un modèle réellement exécuté.
5. **Questions** : /copilot. Si une connexion LLM ne fonctionne pas, montrer l'historique et expliciter le périmètre testé ; ne pas prétendre à une conversation DGX en direct.

## Narration fidèle
- « Le système peut présenter des investigations IA documentées sur des runs historiques, puis confronter une recommandation à des restrictions d'autonomie. »
- « Dans l'histoire Paie, les échanges Claire/management et le blocage par STOP_AUTO sont **simulés**. Aucun load balancer n'a été redémarré. »
- « Le dernier run DGX enrichi identifié (RUN-56C124FC8F7A0490) s'est arrêté à INTELLIGENCE_UNAVAILABLE. Ce n'est pas une preuve de succès Analyst/Critic. »
- « Le registre SQLite, les garde-fous et les API Policy ont des tests isolés ; la coupure des effets LIVE et la coordination multi-instances restent à intégrer/qualifier. »

## Si quelque chose échoue pendant la présentation
- HTTP indisponible : ne pas déployer en direct. Vérifier /health puis passer à un support de présentation hors ligne préalablement préparé.
- Boutons défectueux : utiliser l'histoire métier verbale ; ne pas présenter le scénario interactif comme qualifié sur la session en cours.
- LLM indisponible : présenter le run DGX historique et les limites ; ne pas retenter des commandes affectant l'infrastructure.
- Policy indisponible : ne pas annoncer des KPI ni une autorisation LIVE. Montrer uniquement les tests et la simulation.

## Après démonstration
La prochaine étape technique est l'interposition effective du garde-fou au dernier point d'exécution, la gestion des actions en cours et la qualification multi-instance. Ces travaux nécessitent un environnement de validation séparé.
