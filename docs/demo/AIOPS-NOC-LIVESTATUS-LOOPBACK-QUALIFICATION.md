# NOC — Collecteur TCP Livestatus de qualification sur loopback

**Statut : collecteur réel par socket TCP, restreint à une cible locale explicite ; qualification uniquement sur faux serveur.**

Le module `demo/noc_livestatus_loopback.py` envoie exclusivement la requête Livestatus `GET hosts / Columns: name state plugin_output / OutputFormat: json`, en écoute sur `127.0.0.1` ou `::1`. Il refuse toute adresse réseau distante, impose un port et un timeout bornés, limite le flux à 256 Ko, vérifie les colonnes et convertit le résultat via `demo.noc_livestatus_import.normalize_livestatus_hosts`.

Un test d'intégration ouvre un vrai socket sur `127.0.0.1`, reçoit et vérifie les octets de la requête, puis renvoie une réponse JSON synthétique. Les autres tests rejettent une cible distante, un en-tête inconnu et un export sans hôtes. GitHub Actions `aiops-rag-ops-fixtures.yml` lance désormais ces tests.

Le résultat porte toujours `collection_transport=TCP_LOOPBACK_ONLY`, `provenance=OPERATOR_EXPORT_UNVERIFIED`, `runtime_authenticated=false` et `live_remediation_authorized=false`. Cette restriction de destination au loopback **ne constitue pas une autorisation de sonder un port localhost de production**. Le collecteur n'est pas intégré au portail Debian, n'accède à aucun conteneur Checkmk/Thruk existant et n'authentifie pas la source réseau.

**Prochaines étapes :** collecter les états services, introduire une preuve d'origine du flux et un contrat d'accès contrôlé pour un environnement d'intégration dédié, puis associer Checkmk/Thruk au tableau de bord et à la timeline STAR. Préserver la stack `aiops_noc` historique.
