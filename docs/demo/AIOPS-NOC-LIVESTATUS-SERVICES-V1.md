# AIOps NOC — Collecte Livestatus des services Checkmk (qualification isolée)

## Objectif et réalisation
La collecte TCP précédemment réalisée sur `GET hosts` est étendue à `GET services` via `demo/noc_livestatus_services.py`. La requête demande strictement les colonnes `host_name description state plugin_output`, avec `OutputFormat: json`. Le transport est limité aux littéraux de loopback `127.0.0.1` et `::1` : aucune connexion directe à la machine Debian distante n'est possible depuis ce module.

La réponse normalisée comprend plusieurs services par hôte (sans les confondre avec un doublon), leur état `OK/WARN/CRIT/UNKNOWN`, la sortie du check, une date de capture UTC et sa fraîcheur contrôlée. La validation rejette doublons de couple hôte/service, colonnes inattendues, états inconnus ou booléens, format incohérent, données périmées/futures et réponse surdimensionnée.

## Qualification
`tests/test_noc_livestatus_services.py` contient cinq tests, dont un qui ouvre un **vrai socket TCP local simulé** et vérifie les octets de la requête. Le workflow `aiops-rag-ops-fixtures.yml` est étendu. **Le succès de l'exécution CI du commit courant doit être constaté avant toute revendication de qualification.**

## Limites
Le collecteur n'est pas connecté au Checkmk historique, à Thruk, au portail :17777 ni au RAG opérationnel. Son attribut `provenance=LOOPBACK_UNVERIFIED` et `runtime_authenticated=false` rappelle que les réponses TCP ne constituent pas une authentification du service réel. Aucune modification, acquittement ou remédiation ne sont effectués. L'utilisation du loopback ne constitue pas en soi l'autorisation d'interroger une production locale.

## Prochaine priorité
Faire fusionner, dans un modèle de lecture seule, états hôtes et services, horodatages et informations d'impact, puis présenter la synthèse dans le dashboard NOC avec un marquage de provenance. Prévoir ensuite des adaptateurs réalistes à la stack historique Checkmk/Thruk après audit des composants existants.
