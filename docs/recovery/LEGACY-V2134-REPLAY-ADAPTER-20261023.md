# V2.13.46 — récupération ciblée du replay historique V2.13.4

**Statut : code d'adaptation offline testé localement ; aucune promotion du portail :17777 ni du runtime Debian.** Les archives privées ne sont pas commitées. Aucune donnée opérateur ni capture réelle n'est publiée.

## Sources originales identifiées et dédupliquées

| Archive / version / SHA-256 archive | Chemin d'origine | SHA-256 du membre | Décision |
|---|---|---|---|
| AIOPS-V2.13.4-HYBRID-REPLAY-STAR.zip / V2.13.4 / 83d71029197e0c23310a5e466ad68dfcb6e04683160bc3e0e5b9302edbe85550 | tools/build_real_replay.py | f71a568f4229402a6f6b5238552efbdd18fa41320c8c285afedc386812bbb97d | Original complet (12 103 octets), conservé en archive privée ; **non** promu comme moteur sécurisé |
| même archive | tools/assemble_hybrid.py | ffce55bf4c100642e751e73857a90e50b6f9bc030e4caba8f2bc71268db437d3 | Déjà présent dans recovery/legacy_v2134/tools/assemble_hybrid.py : ne pas dupliquer |
| même archive | tests/test_replay.py | e1fadcf8c20ab19ba1e696aa11237f42ec300a64ce9745b496023648eaaef8aa | Original complet ; cinq tests exécutés localement en environnement isolé |
| AIOPS-V2.13.6.1-HYBRID-FINAL.zip / V2.13.6.1 / 0f382f64a3da7ad0e81c3fde33a2c800ea73844f1ea7f38711ab7b17979a5f29 | 01-Demo/tools/build_real_replay.py | f71a568f4229402a6f6b5238552efbdd18fa41320c8c285afedc386812bbb97d | Copie **strictement identique** à V2.13.4 ; ne pas restaurer une deuxième fois |
| AIOPS-V21310-STAR-PORTAL.zip / V2.13.10 / cdca139131dbbac7adb2f811077c25e94dd01899a6ec33c37ea067d26a351d87 | portal_demo_public_v21310.py | 5bee897914ec958af0f715f24eee229b9f9539a3df5da4f9c43cb8746ad60ee0 | Comparé au module courant app/portal/portal_demo_public_v21310.py ; préserver la version courante |

## Besoin, interfaces et architecture

**Besoin métier :** rejouer de façon déterministe une séquence historique SAN/Payments, de l'ingestion au diagnostic Analyst/Critic puis à la décision Policy, sans inventer de preuve, d'identité ou de remédiation. L'ancien générateur V2.13.4 accepte uniquement DEMO/BLOCKED, produit un HTML offline et dépend d'exports Core run.json, ai-ledger.json et evidence.json. Il ne convient pas tel quel au scénario synthétique récent DEMO/RESOLVED.

**Adaptation livrée :** demo/star_legacy_replay_adapter.py fournit la fonction pure build_replay(run, ledger, evidence) et le schéma star-core-legacy-replay/v1. Elle accepte DEMO/BLOCKED et DEMO/RESOLVED, refuse LIVE et les identités run_id divergentes, exige les références Evidence connues et uniques (y compris les identifiants historiques courts comme E1), et émet seulement des champs explicitement autorisés (sévérité P1/P2/P3, booléen validated, confidence finie de 0 à 1). Les identifiants Evidence et les valeurs libres du journal ne sont jamais recopiés dans les frames.

**Chronologie :** tri stable uniquement si chaque enregistrement porte un timestamp exploitable avec fuseau. Dans le cas contraire, l'ordre des collections est conservé et la chronologie est explicitement non prouvée. Les trois empreintes SHA-256 portent sur la représentation JSON canonique des objets en mémoire, **pas** sur les octets originaux des fichiers exportés et **pas** sur leur origine runtime.

**Dépendances :** Python 3.12, bibliothèque standard ; aucun FastAPI, Playwright, n8n, GLPI, Grafana, Temporal, DB, secret ou port requis. Le module est un adaptateur de données et **n'est pas branché au portail**. Une intégration future doit respecter star-portal-transport-v1, la cinématique à neuf checkpoints et la séparation des preuves authentiques/synthétiques.

## Qualification effectivement réalisée (23 octobre 2026)

- 10 tests unitaires nouveaux : PASS, fixtures exclusivement synthétiques.
- 5 tests originaux V2.13.4 : PASS en répertoire temporaire, sur fixtures synthétiques.
- Assemblage complet V2.13.4 : PASS dans un répertoire temporaire avec les trois pages HTML originales et des exports synthétiques DEMO/BLOCKED ; aucune API appelée.
- Compilation Python du nouvel adaptateur et des tests : PASS.
- CI dédiée : PASS sur le commit GitHub initial, puis nouvelle qualification à contrôler après correction de compatibilité E1 ; ne pas confondre avec qualification Debian.
- Les tests historiques **ne** prouvent **pas** la sécurité de diffusion des pages originales. Le script ancien intègre des métadonnées opérateur dans du HTML et reste quarantainé.

## Limitations, migration et retour arrière

Aucune capture n8n/Grafana/GLPI n'a été effectuée ; pas de preuve runtime, pas d'approbation HITL réelle, pas de clôture métier ni d'exécution LIVE. Les fichiers complets F20.13 Playwright restent à retrouver dans les archives privées, les fragments de conversation étant insuffisants. La prochaine migration doit relier les sorties de cet adaptateur aux cues du portail via un schéma versionné et des tests d'intégration **sans** import en production.

**Rollback :** supprimer les nouveaux fichiers demo/star_legacy_replay_adapter.py, tests/test_star_legacy_replay_adapter.py, le workflow CI et cette fiche dans la branche de PR. Aucun état applicatif ni DB n'a été modifié. PR draft, aucun merge.
