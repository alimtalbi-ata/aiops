# Data model

`runs` is the canonical execution object. `run_events` is its immutable journal. `run_stage_state` provides a materialized stage view. `command_receipts` and `execution_receipts` provide idempotency.

`evidence` is immutable and hashed. `gates` bind decisions to evidence. `twin_nodes`, `twin_edges` and `twin_facts` represent the Digital Twin. `incidents`, `observations`, `changes` and `impact_assessments` provide operational context. `scenarios` and `scenario_steps` make synthetic demonstrations deterministic.
