# Demo / Replay / Story

The mode belongs to the Run, not to a global switch. This prevents a global `simulation_only` flag from accidentally changing the safety semantics of another Run.

- **DEMO**: deterministic synthetic scenario, visually optimized for demonstration.
- **REPLAY**: deterministic reproduction of an earlier event sequence.
- **STORY**: scripted narrative using the same execution model.
- **LIVE**: production evidence only; synthetic mutation endpoints are rejected by design.


## Presenter-first Demo Studio

The Portal exposes a static presenter aid at `/demo/studio`. It provides a five-minute French-language walkthrough for the synthetic ACME SAN P1 → Payments P2 scenario, linking the existing impact view, Explore/Story timeline and read-only ITSM handoff.

The Studio is deliberately static: it does not load fixtures, call Core/GLPI/NOC, create Runs or tickets, store credentials, or trigger actions. It repeats the simulation boundary and presenter narration so an operator can explain the demo consistently. Its route test is included in the quality workflow. This is presentation guidance, not evidence of runtime integration or qualification.
