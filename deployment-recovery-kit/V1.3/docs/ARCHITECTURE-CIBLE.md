# Target architecture — controlled recovery

- **Source of truth:** versioned source and SHA-256 manifests, not Docker labels alone.
- **Active runtime:** preserve during discovery; scripts default to read-only.
- **V69 candidate base:** event gateway, context, causal analysis, policy, simulator/chaos, RAG, observability, console, HITL/GLPI and remediation components.
- **Temporal:** validate address, namespace and task queue from verified configuration. Do not assume values from variable names.
- **Staging:** copy sources into a new, separate directory; preserve original sources.
- **Deployment gate:** exact Compose validated, images available/rebuildable, health/contracts tests passed, approval recorded.

```text
Runtime inventory -> source/config collection -> hash/compare
 -> isolated staging -> Compose validation -> tests
 -> security review + backup -> explicit approval -> controlled deployment
```

This is a reconstruction plan, not certification that the current runtime can be recreated from the discovered files.
