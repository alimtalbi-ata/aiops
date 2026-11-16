# ACME Evidence Center — V2.12.8 offline integrity

## Scope
Fail-closed SHA-256 verification of the three offline HTML pages against the existing V2.12.4-format manifest. The manifest version describes generated content; 2.12.8 describes the verifier.

## Run on Debian
```bash
cd /home/aiops/aiops-v28-demo
python3 -m unittest discover -s tests -p 'test_verify_offline_manifest_v2128.py' -v
python3 tools/verify_offline_manifest_v2128.py --kit /tmp/acme-evidence-center-v2127/kit --report /tmp/aiops-v2128-integrity-report.json
```

## Security checks
Reject modified, missing, duplicate, unexpected, symlinked, path-traversing, and malformed entries. The verifier is local, offline, does not execute remediations, and does not access Core/DGX.

## Attestation limits
The manifest is **not cryptographically signed**. SHA-256 comparisons prove only local consistency, not source authenticity. Preserve historical provenance and separate synthetic scenario evidence. Independently attested DGX inference: **false**. Qualified LIVE execution: **false**. Browser navigation and policy executor fencing require separate qualification.

## Deployment precautions
Do not overwrite or commit local untracked Compose files (`compose.demo-local.yml`, `compose.dgx-network.yml`, `compose.llm-test.yml`). Preserve the production stack. Changes are developed on the feature branch pending review.
