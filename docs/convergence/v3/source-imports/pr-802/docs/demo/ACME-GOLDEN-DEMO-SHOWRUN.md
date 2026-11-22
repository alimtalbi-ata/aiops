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

## Debian operator recipe — explicit sandbox authorization required

The GitHub bridge's `status` command **cannot** run the E2E test, install a
branch, or capture screenshots. A GitHub PR or a green CI check is **not**
evidence that the Debian host has the matching version. The following commands
are for an authorized Debian operator **only**, after verifying the running
containers are the isolated ACME test stack and obtaining approval to execute
the synthetic scenario. Never execute against LIVE or customer tenants.

```bash
# From an approved checkout of the exact revision actually deployed.
git rev-parse HEAD
python3 deploy/debian-acme-sim-e2e.py
# WARNING: runner exits 0 for both PASS and BLOCKED. Inspect the receipt.
python3 scripts/acme_demo_readiness.py \
  /home/aiops/.local/state/aiops-debian-agent/acme-sim-e2e.json
```

The E2E runner performs synthetic POSTs to the sandbox simulator and Core, so
**it is not a read-only status probe**. It checks all five capabilities first,
then verifies the Worker no-effect receipt and independent terminal readbacks.
If any capability is absent, expect `BLOCKED`, not an invented successful
test. The offline readiness command exits 0 only for `GO_SIMULATION_ONLY`
and exits 2 for `NO_GO`. A successful verdict never authorizes LIVE.

Publish the **sanitized** report and screenshots back through the approved
GitHub evidence workflow, with the exact executed SHA, UTC collection time,
scenario, mode, readiness verdict, and per-scene `PASS`/`BLOCKED`/
`NOT_IMPLEMENTED`. Review screenshots and JSON for internal hostnames,
secrets, tokens, customer data and identifiers before publication. If GitHub
publication is unavailable, record `EVIDENCE_NOT_PUBLISHED` and keep NO-GO.
Do not claim screenshots exist until they are actually captured.

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
