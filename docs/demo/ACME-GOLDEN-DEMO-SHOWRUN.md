# ACME SAN → Payments — golden demo showrun

**Audience:** NOC, IT operations, customer sponsor. **Mode:** isolated SIMULATION only.
**Duration target:** 8–10 minutes. **LIVE:** NO-GO. No paid OpenAI API or Codex.

## Preflight (mandatory, before opening the demo)

1. Identify the **exact deployed commit SHA** and isolate ACME-TEST from customer tenants.
2. Run the existing ACME sandbox capability preflight against Simulator, Core, Twin,
   Policy and Worker. All five must attest isolated SIMULATION, no LIVE effects,
   no real GLPI writes and no claimed human approval.
3. Obtain a fresh `acme-sim-e2e.json` from the existing Debian sandbox runner
   `deploy/debian-acme-sim-e2e.py`; do not fabricate a PASS.
4. Check: `python3 scripts/acme_demo_readiness.py /path/to/acme-sim-e2e.json`.
   Only `GO_SIMULATION_ONLY` permits the **sandbox presentation**; anything else
   is NO-GO, not an invitation to bypass Policy.
5. Test the actual Portal page, source badges, screen sharing, keyboard navigation,
   and responsive layout on the **deployed** version. Capture evidence and timestamps.
6. If preflight fails, use the labeled prerecorded *simulation* walkthrough,
   never a fabricated live execution.

## 8–10 minute narrative

| Time | On screen | What the audience should understand | Evidence gate |
|---|---|---|---|
| 0:00–0:45 | NOC overview, SIMULATION watermark | One business service at risk: Payments | Tenant and mode visible |
| 0:45–1:45 | Seven synthetic SAN/infra observations | Several signals converge into one incident | Source IDs, freshness, deduplication |
| 1:45–3:00 | Dependency path SAN → storage → Payments | Business impact explained, not guessed | Twin path provenance; UNKNOWN if missing |
| 3:00–4:30 | Analyst hypotheses vs Critic objections | The system distinguishes evidence from uncertainty | Independent citations and contradictions |
| 4:30–6:00 | Policy gate and simulated approval | No autonomous production remediation | HITL not falsely claimed; no effect allowed |
| 6:00–7:30 | Simulated ITSM ticket + Worker receipt | Traceable workflow with no real GLPI write | Matching ticket/incident/run IDs, digest |
| 7:30–9:00 | Final timeline and exportable proof | Audit-ready explanation of what happened | Fresh PASS receipt and exact SHA |
| 9:00–10:00 | Safety recap and business value | Faster triage, with human authority preserved | Explicit SIMULATION / LIVE NO-GO |

## Red lines

- Do not label mocked metrics as real monitoring or a simulated approval as HITL.
- Do not claim root cause when the graph is inferred or sources are missing.
- Do not call a simulation PASS an E2E LIVE PASS.
- No real ticket writes, remediation, deployment, secrets or paid OpenAI API.
- If a page/step does not exist in the deployed Portal, mark **NOT_IMPLEMENTED**
  and fall back to a transparent narrated screenshot rather than inventing it.

## Acceptance evidence to collect

Deployed SHA, five capability receipts, E2E receipt and freshness, readiness
verdict, screenshots of each scene, responsive/keyboard results, CI exact-SHA,
and one owner for each missing scene. A script and unit tests alone are NOT
proof that this showrun has been performed.
