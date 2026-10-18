# Naming, ports and networks

Container names: `aiops-<component>` only. No historical version suffixes.

Internal application ports use three digits: Core 810, Twin 811, Evidence 812, Policy 813, Copilot 814, Worker 815, Simulator 816, Portal 777. Portal is exposed as **7777**. Standard external ports remain GLPI 8080, n8n 5678, Prometheus 9090, Grafana 3000, Alertmanager 9093. Temporal 7233 is internal only.

All custom UI ports should use 77xy when externally exposed, except applications with an established standard port.
