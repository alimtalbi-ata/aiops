# AIOps NOC — Vue unifiée hors ligne avec provenance séparée

Le module `demo/noc_unified_offline.py` assemble dans un seul document deux tableaux de bord existants :

1. **Scénario ACME SYNTHÉTIQUE** : tableau de bord `noc_wallboard.py` (six événements multiconstructeurs, topologie SAN, runbooks simulés).
2. **Checkmk EXPORT NON AUTHENTIFIÉ** : `noc_checkmk_offline_wallboard.py` (hôtes/services issus de fichiers normalisés, date et ancienneté de la capture).

Chaque volet est rendu dans une iframe `srcdoc` séparée avec attribut `sandbox=allow-scripts` et sans `allow-same-origin`. Les contenus sont échappés pour l'attribut HTML. Aucun contenu réel non fiable ne doit recevoir les mêmes privilèges que la page parente. Il n'existe aucun code de fusion ou de promotion de statut entre simulation et export non authentifié.

## Génération
```bash
python -m demo.noc_unified_offline checkmk-hosts-normalized.json checkmk-services-normalized.json --output /tmp/aiops-noc-unified.html
```

La commande crée un fichier HTML autonome, sans réseau, et n'écrase pas un fichier existant. Les sources `checkmk-hosts-normalized.json` et `checkmk-services-normalized.json` doivent correspondre au contrat exact du module de consolidation ; les fichiers test ne démontrent aucune connexion à Checkmk ou Thruk réel.

## Limites et sécurité
**Ce travail n'est pas encore déployé sur le portail Debian :17777.** Aucune collecte en production, aucun acquittement, aucune ouverture des ports historiques 8119/8120, aucune action GLPI/n8n et aucune remédiation LIVE. Une capture Chromium de ce document serait une capture de **deux vues hors ligne**, pas la preuve de fonctionnement de la supervision.

`tests/test_noc_unified_offline.py` qualifie la séparation, la sandbox, le rejet de revendications LIVE et l'échappement des champs. Le workflow `aiops-rag-ops-fixtures.yml` exécute ces contrôles ; vérifier son résultat au dernier SHA.

## Suite
Créer un script de génération de deux exports de tests déterministes et le qualifier dans un navigateur réel Chromium. Après audit du NOC historique, intégrer via une route DEMO explicitement isolée à l'interface AIOps, puis travailler sur une collecte vraie avec preuve de source, sous autorisation.
