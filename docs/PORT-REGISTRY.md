# AioOps 2.0 — Port Registry

| Service | Docker | VM | Exposure |
|---|---:|---:|---|
| Portal | 777 | 7777 | external |
| GLPI | 80 | 8080 | external |
| n8n | 5678 | 5678 | external |
| Prometheus | 9090 | 9090 | external |
| Grafana | 3000 | 3000 | external |
| Alertmanager | 9093 | 9093 | external (optional) |
| Temporal gRPC | 7233 | — | internal |
| Temporal UI | 8080 | — | internal |
| Core | 810 | — | internal |
| Twin | 811 | — | internal |
| Evidence | 812 | — | internal |
| Policy | 813 | — | internal |
| Copilot | 814 | — | internal |
| Worker | 815 | — | internal |
| Simulator | 816 | — | internal |

Internally developed UI exposed from the VM must use the `77xy` family; the main Portal is `7777`.
