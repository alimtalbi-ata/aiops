# AIOps 2.0 — Clean-Slate V8.0.0

Reconstruction fonctionnelle de la plateforme AIOps. Les anciennes stacks restent hors runtime et ne sont jamais arrêtées par le kit.

## Chemin canonique
Simulator/Ingress → Core → Run → Temporal → Twin + Evidence + RAG → Intelligence → Critic → Policy → HITL/Remediation → Verify/Reconcile → Integration/Outbox → GLPI/n8n → Portal projection.

## Modes
LIVE, DEMO, REPLAY, STORY. DEMO/REPLAY/STORY sont explicitement synthétiques/rejoués et ne mutent aucun système externe.

## Ports externes
Portal 7777, GLPI 8080, n8n 5678, Prometheus 9090, Grafana 3000.

## Ports internes
Core 810, Twin 811, Evidence 812, Policy 813, Copilot 814, Simulator 816, Integration 817, Intelligence 818, RAG 819, Temporal 7233, PostgreSQL 5432, MariaDB 3306.
