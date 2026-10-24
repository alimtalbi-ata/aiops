# Recovery card — summarize_core_historical_v2125.py

**Origin:** archive `AIOPS-V2.12.5-Historical-Summary-Source.zip`, uploaded via historical ChatGPT AIOps work in October 2026. This directory intentionally preserves a **legacy** file and its original tests; no runtime deployment is implied.

**Original context:** Core/AI Ledger/Evidence historical run exported by an authenticated operator; used to produce a bounded and non-sensitive numerical summary for an offline Evidence Center and Executive STAR replay.

**Purpose:** ensure consistent `run_id` in run/ledger/evidence, count event/stage/analyst/critic/policy records, detect duplicate evidence IDs and missing references, and avoid claiming independently verified DGX or LIVE operation.

**Inputs:** three JSON objects with `run`, `events`, `stages`, `analyses`, `critiques`, `policy_decisions`, and `items`. **Outputs:** summary JSON, not raw evidence. Depends only on Python standard library.

**Qualification scope:** source and four upstream unit tests recovered. Run offline: `cd recovery/legacy/v2125 && python3 -m unittest -v test_summarize_core_historical_v2125.py`. The original code has a **hardcoded historical RUN ID**, making it unsuitable as a generic service without a safer, reviewed configurable identity contract. Tests do not qualify integration with live Temporal/DGX/GLPI.

**Security:** Never use on unrestricted unreviewed exports without size limits, sanitation and separate path policy. Never replace production workflow or weaken cross-run identity checks. This is a reference baseline for adaptation, not a production candidate.

**Reuse recommendation:** parameterize expected run identity, add schema/size controls and strict evidence provenance, compare against the newer `demo/star_capture_evidence.py` workflow before merging functionality.
