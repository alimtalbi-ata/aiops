# V7.5 architecture review

V7.5 introduces explicit RAG and Intelligence boundaries and closes the run-state gap where a blocked policy stage could leave the Run in RUNNING.

The integration boundary remains isolated. Internal application ports are never published. Simulation state is scoped to run_id and observations are tagged with run_id.

A model adapter is intentionally not fabricated: Intelligence returns an explicit UNKNOWN/zero-confidence result until a real local/cloud model adapter is configured.
