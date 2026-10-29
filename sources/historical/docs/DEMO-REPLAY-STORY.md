# Demo / Replay / Story

The mode belongs to the Run, not to a global switch. This prevents a global `simulation_only` flag from accidentally changing the safety semantics of another Run.

- **DEMO**: deterministic synthetic scenario, visually optimized for demonstration.
- **REPLAY**: deterministic reproduction of an earlier event sequence.
- **STORY**: scripted narrative using the same execution model.
- **LIVE**: production evidence only; synthetic mutation endpoints are rejected by design.
