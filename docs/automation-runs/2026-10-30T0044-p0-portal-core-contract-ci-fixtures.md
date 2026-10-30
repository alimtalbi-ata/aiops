# 2/5 Portail — correction des fixtures Core après CI rouge (30/10/2026)

- **Parent :** `d84b582832521ab1fa03476a8cf0222134603e30`, PR unique #185. La CI V2.8 du parent `40974998799` a échoué : 3 échecs + 3 erreurs, car `tests/test_v28_portal_ui.py` utilisait des réponses de détail Core plates ou un objet `run` sans `run_id/mode`. Ces fixtures ne respectent pas le contrat réel `detail.run`.
- **Correction :** mise à jour de sept fixtures existantes avec `run_id` et `mode=DEMO` concordants ; tests de non-fabrication conservés. Aucun assouplissement du garde fail-closed de `app/portal/main.py`, aucune nouvelle fonctionnalité.
- **Tests locaux : NOT_TESTED** ; attendre `quality.yml` et V2.8 du SHA exact. Le parent est **CI rouge**, ne pas promouvoir.
- **Packaging et terrain :** inchangés, `main.py` IMAGE_TRANSPORT du déployeur candidat, non couvert par le cron portal-only. Debian, `applied.sha`, rollback et smoke : NOT_TESTED. READY_FOR_STABLE=BLOCKED / DEMO_READY_DEBIAN=NOT_READY.
