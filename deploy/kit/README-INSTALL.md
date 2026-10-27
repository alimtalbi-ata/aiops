# AIOps — kit de déploiement candidat

**Point d'accès cible unique :** http://10.79.94.202:17777/

## Installation guidée Debian 13

1. Décompresser le kit.
2. Lancer le préflight sans modification :

```bash
chmod +x install-aiops-candidate.sh
sudo ./install-aiops-candidate.sh --audit
```

3. Examiner les sorties (HTTP du portail, espace disque, inventaire Docker/ports).
4. Après approbation, récupérer le code dans un répertoire candidat isolé :

```bash
sudo ./install-aiops-candidate.sh --install
# ou
sudo ./install-aiops-candidate.sh --install --dest /opt/aiops-candidate
```

## Portée exacte

Le mode par défaut est en lecture seule. `--install` clone/met à jour le code de la branche candidate uniquement. Le script **ne** lance pas Docker Compose, ne modifie pas les services de production, ne crée pas d'autre port, ne touche pas au pare-feu ou à systemd, ne monte pas les routes NOC et ne redémarre aucun composant.

Ce kit est un **bootstrap d'installation candidat**, pas encore un installateur complet de toute la plateforme. L'intégration du routeur NOC au processus réel du portail et le test E2E sur Debian restent à qualifier avant toute bascule de production. Les tests offline/synthétiques ne prouvent pas un fonctionnement live.
