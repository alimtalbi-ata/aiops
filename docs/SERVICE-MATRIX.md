| Component | Port | Network | Authority / role |
|---|---:|---|---|
| Portal | 777 | public/control | operator UI |
| Core | 810 | control/data | Run authority |
| Twin | 811 | control/data | topology/state authority |
| Evidence | 812 | control/data | provenance authority |
| Policy | 813 | control | safety gate |
| Copilot | 814 | control | evidence-first assistant |
| Worker | 815 | control/execution | Temporal client/worker |
| Simulator | 816 | execution | synthetic source |
| Temporal | 7233 | control/temporal-data | workflow executor |
| GLPI | 80→8080 | integration | ITSM/CMDB integration |
| n8n | 5678 | integration/control | external integration |
| Prometheus | 9090 | observability/control | metrics |
| Grafana | 3000 | observability | dashboards |
| Alertmanager | 9093 | observability | alerts |
