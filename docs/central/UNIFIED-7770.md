# CENTRAL — portail unique 7770
Decision PO: no new standalone POC. Preserve historical portal features. Target UI 7770 only; existing instances remain rollback until acceptance.

Base source candidate: integration/portal-bounded-runs-consolidated-20261111 (app/portal/main.py includes NOC runtime, correlation, demo RAG, Grafana health, ACME impact/explore/run detail and GLPI operator view). Exact deployed historical image/source equivalence not established; do not overwrite it.

Parallel deliveries on existing team branches:
- A: additive navigation and panels in historical portal; reuse PocTechnical and PocDemo only where they add functionality, not replacement shell.
- B: connect historical technical and business read models; render all available aggregate KPI and history. Reuse fa753a670895df1c0382d5a7ff7dc0d6ff5e606c.
- C: preserve historical NOC/RAG/Copilot paths; connect actual DEV inference and orchestration where supported; reuse 67feba7a5601c8629d365848a800048f217b3242 without claiming synthetic API is real LLM.
- D: compare historical portal baseline and unified target, functional journeys, no feature loss. Reuse decfc02717dd4ca9f2996078cee741f4a0340312 where applicable.
- CENTRAL: single integration commit and installation script, deploy 7770 once; retain earlier versions until browser acceptance. No new port, no public secrets, no destructive operations.

Previously validated POC02 build and snapshot/journey HTTP200, not browser acceptance. A f5ac26ce0070d724d24d8975b33e0500f36af9f7. All contributions must supply exact SHA and runnable tests. GitHub only.
