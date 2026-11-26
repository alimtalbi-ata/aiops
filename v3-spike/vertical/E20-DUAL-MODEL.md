# E20 dual-model advisory boundary — experiment

Status: candidate; no production or actual model quality claim. Reuses the E18
server-verified historical correlation projection, and the measurement principles
from historical PR #196 (747f0df4b8bae0fa0265b6dc568558a6a9057ad1,
AI-INVOCATION-TELEMETRY-IMPLEMENTATION.md). No code or branch from #196 imported.

Two explicitly configured distinct loopback endpoints and model labels are required.
Model identity/independence is not attested by distinct labels. No default provider,
external network, secrets, tools, remediation, retries or fallback. Only bounded
structured synthetic candidate data is submitted; raw documents/logs are excluded.
Analyst selects or abstains; Critic challenges, agrees as candidate only or abstains.
All citations must match exact candidate evidence IDs. Reverse or unresolved order
cannot be promoted by model agreement. Deterministic E18 and DENY remain authoritative.

Actual HTTP transport tests use two synthetic fixture servers, not inference.
Run: python3 -m unittest discover -s v3-spike/vertical -p test_dual_model_advisory.py -v

Telemetry: measured wall latency, bounded bytes and output-token request parameter,
provider-reported complete token counts only, missing usage null, cost and TTFT null.
No raw response persistence, no token estimates. No authenticated tenant ACL,
provider attestation, RAG prompt ingestion, live model benchmark, durable telemetry,
or GAMMA/HTTP production wiring in this increment. Socket timeout is not a hard
end-to-end deadline; qualify cancellation, quotas and resource budgets before real
provider deployment. Next: reuse/qualify local model adapter, pin model digests,
benchmark actual two-model inference with counterexamples and independent D review.
