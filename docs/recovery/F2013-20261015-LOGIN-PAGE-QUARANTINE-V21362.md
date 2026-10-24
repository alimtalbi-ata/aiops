# F20.13 — Provenance des captures Playwright du 15 octobre 2026

## Sources et empreintes vérifiées localement

| Original dans la bibliothèque | Taille (octets) | SHA-256 des octets originaux | État |
| --- | ---: | --- | --- |
| `Texte collé(20261015-155410).txt` | 11457 | `d742b21dbb27ac16d4122e1ceab7b5de39325985999ae2e81a97af29fdf64432` | journal textuel, script tronqué |
| `Texte collé(20261015-155749).txt` | 19525 | `65611d3d0cc4abe26e958281dbaf854543d3c14c80a8c8036d60d79cc5f1aa12` | journal textuel, script tronqué |

Ces fichiers sont des extraits de conversation, pas des archives des scripts originaux. Ils ont été matérialisés en lecture seule depuis la bibliothèque, puis hachés localement. **Aucun journal brut n'est publié dans le dépôt.**

## Contexte métier, interfaces et architecture

Ancien kit `AIOps-UCP-F20.13-EVIDENCE-DEMO-KIT-v0.2`, script cité `scripts/demo-multistack-capture.py`. Il utilisait Python et Playwright/Chromium pour naviguer dans l'UCP et tenter des captures des applications locales GLPI (8080), n8n (5678), Grafana (3000), ainsi que Kibana/Prometheus. Sorties historiques mentionnées : PNG et `DEMO-MULTISTACK-MANIFEST.json`.

Les journaux décrivent une progression vers `PASS=17` / `FAIL=0`, **mais ce résultat signifie uniquement que le collecteur a produit une capture HTTP/navigation selon ses critères**. Les observations consignées incluent :

- GLPI : titre `Authentication - GLPI` (page de connexion, pas fiche ticket).
- n8n : redirection vers `/signin` (page de connexion, pas exécution de workflow).
- Grafana : redirection vers `/login` (page de connexion, pas dashboard d'alerte).
- UCP : correspondances de sélecteurs `automation_hitl` et `reports_kpi` corrigées dans le journal.

**Conclusion :** les 17 captures historiquement « PASS » ne prouvent ni un état métier, ni une session authentifiée, ni l'identité de l'incident, ni la présence des neuf écrans STAR au bon checkpoint. Ne jamais les promouvoir en preuves réelles.

## Réutilisation et dépendances

À réutiliser : taxonomie d'applications, noms de vues UCP, échecs de sélecteurs observés, protocole de rapport PASS/FAIL, et besoin d'un contrôle explicite de la page métier après authentification.

À ne pas réutiliser sans récupération et audit des fichiers originaux complets : script `demo-multistack-capture.py` (le heredoc du journal est visiblement corrompu/tronqué), état des sessions navigateur, captures originales, authentifiants, commandes d'accès runtime. Ne pas exécuter les anciennes commandes de navigation sur Debian.

Les modules modernes `demo/star_snapshot_browser.py`, `demo/star_browser_manifest_gate.py`, `demo/star_capture_execution_worklist.py` et leurs tests synthétiques sont les références de développement ; comparer SHA et fonctionnalités avant toute importation du patrimoine.

## Conditions de qualification / rollback

Avant réutilisation : retrouver le script complet et son SHA, comparer les interfaces et dépendances, vérifier absence de secrets, reconstruire des tests Chromium **isolés**, refuser les redirections login/signin et les captures sans `run_id`/`event_ref`/état métier. Ne pas utiliser de screenshots fictifs comme preuve réelle. Cette fiche n'active aucun code historique ; rollback par revert du seul commit documentaire.

## Limites

Les empreintes ci-dessus attestent uniquement l'identité des deux journaux récupérés. Elles ne sont pas les SHA des scripts Python originaux, ni des PNG. Aucun test E2E Debian n'a été exécuté.
