# D01 runtime smoke FIX01
Run on approved test checkout, not production image. Node 22. From qa/mission-control:
```sh
set -eu
umask 077
test -f package-lock.json
npm ci
npm audit --audit-level=high
npx playwright install chromium
BASE_URL='<approved origin>' npm run preflight
BASE_URL='<approved origin>' UI_PATH='/mission-control' npm test -- smoke.spec.cjs
```
Qualification requires the reviewed committed lockfile. If absent, STOP; CENTRAL may generate it separately with npm install --package-lock-only --ignore-scripts on the approved network and submit it for review. UI_PATH must be confirmed by CENTRAL. No secrets for this suite; no authenticated tests, no simulation POST. Browser blocks non-read methods. Reports/traces may contain sensitive server data: keep private, never publish raw artifacts. This suite is runtime only; no mocks and no runtime PASS claimed.
For isolated A/B/C tests use assembled checkout including C test overlay 8144ebc9252d540a3ecd23acbb01007314015414. From root with isolated venv and build-aligned dependencies:
```sh
PYTHONPATH=app python -m pytest tests/mission_data tests/mission_actions -v
cd frontend/mission-control
OUT=$(mktemp -d)
./node_modules/.bin/tsc --strict --target ES2020 --module commonjs --outDir "$OUT" src/ux/operational.test.ts src/ux/analytics.test.ts && node "$OUT/operational.test.js" && node "$OUT/analytics.test.js"
OUT=$(mktemp -d)
./node_modules/.bin/tsc --strict --skipLibCheck --target ES2022 --module commonjs --lib ES2022,DOM --outDir "$OUT" src/actions/providers.test.ts && node -e 'require(process.argv[1]).verifyProviderContracts().catch(e=>{console.error(e);process.exitCode=1})' "$OUT/providers.test.js"
```
No production secrets or network for unit tests. ACME official fixture required. P1 authenticated API and browser tests are implemented. P2 simulation is not implemented or authorized.

## ACME viewer read-only
Set QA_VIEWER_TOKEN through an approved local secret mechanism, never on a command line or in Git. Run `npm test -- acme-readonly.spec.cjs` with BASE_URL HTTPS or loopback only. No redirects, no traces/screenshots/video for this authenticated API test. Keep all reports private; sanitize before sharing. Missing viewer skips the test, not PASS. No POST or execution. The API checks synthetic classification, incident/run/source binding, affected CI IDs, missing evidence, LIVE ACL refusal. Remove token from environment after testing.

## Container discovery and security gate
Mount the entire assembled checkout at /work (not just qa/mission-control), workdir /work/qa/mission-control. Use matching Playwright image mcr.microsoft.com/playwright:v1.55.1-noble, subject to CENTRAL approval. Verify both ../../tests/e2e/mission-control and package.json exist before installing. Run preflight and confirm all five spec files appear for both projects (14 discovered: 6 anonymous, 2 API, 2 browser, 2 desktop SIM02 entries and 2 mobile read-only entries (non-target projects skipped)). Stop on discovery failure or high audit findings. Proposed 1.55.1 pin addresses the known pre-1.55.1 browser-download TLS verification advisory; CENTRAL reported zero findings on its 1.55.1 installation; repeat audit against the committed lockfile before qualification. Generate and commit lockfile on approved network, then use npm ci for repeat runs. Collect artifacts/ relative to QA workdir, private only. Do not use npm audit fix --force.

## D02 qualification
Use an assembled checkout with exact A/B/C overlays recorded by CENTRAL. Install frontend dependencies with its own npm ci and prepare an isolated Python venv using build-aligned dependencies plus pytest/httpx. Use a network-isolated runner with synthetic fixtures only. From root: `QA_PYTHON=/absolute/path/to/venv/bin/python bash qa/mission-control/run-isolated.sh`. Any failure stops the runner; subsequent suites are NOT RUN. For required authenticated API qualification: `QA_REQUIRE_VIEWER=1 npm test -- acme-readonly.spec.cjs` from QA directory with approved BASE_URL and securely injected QA_VIEWER_TOKEN. Missing viewer is BLOCKED (nonzero); optional suite skips are not PASS. D01 anonymous smoke is separately runnable with `npm test -- smoke.spec.cjs`. No simulation authorization implied.

## D02 browser journey
`QA_REQUIRE_VIEWER=1 npm test -- acme-browser.spec.cjs` with approved viewer and HTTPS/loopback. This test navigates actual ACME panels, verifies source binding, keyboard Twin inspection, disabled simulation, Evidence MISSING, ITSM link (not followed) and return to operational isolation. No Inspecter provider actions or story POST; no operator entered. Browser blocks external origins and non-read methods; no traces/screenshots/video. Preflight must now list five specs for both projects. Private reproduction required for any failure.

## FIX02 closure gate
Record actual checkout SHA, assembled application overlay/image digest, Node and Playwright versions, lockfile SHA256, audit status and per-project test counts. With approved origin and private viewer provisioning, run `QA_REQUIRE_VIEWER=1 npm test -- acme-readonly.spec.cjs acme-browser.spec.cjs`. Keep anonymous and authenticated evidence separate. Require 4 passed, 0 failed, 0 skipped for this selection. Report only sanitized phase labels and counts. CENTRAL local FIX02 patch on D4750a067 passed browser 2/2; do not attribute that receipt to official D4339fc13 or later commits without rerun. No SIM01 authorization follows from this gate.

## SIM02 — CENTRAL authorized run only
Default disabled. After explicit CENTRAL authorization for the exact isolated environment and operator, privately inject distinct QA_VIEWER_TOKEN and QA_OPERATOR_TOKEN, set approved BASE_URL and run `QA_ENABLE_SIM02=1 npm test -- sim02.spec.cjs --project=chromium --retries=0 --repeat-each=1`. Never include SIM02 in the read-only qualification. One POST permitted only after authority and journey checks and exact body binding, other writes blocked; no retry after uncertain result. Browser receipt/evidence, UNKNOWN actual recovery and operational clearing checked. No traces/screenshots/video or raw output sharing. CENTRAL must independently check before/after health and receipt digests. NOT RUN by D; route guard is not a substitute for server authorization or network isolation. Mobile skipped deliberately to avoid a second simulation.

## Mobile and D03
Run the explicitly selected mobile read-only spec as documented in D03.md; no simulation click or POST. Do not run an unfiltered suite with operator credentials. Desktop CENTRAL reports 11/11 steps PASS, browser and validator exit 0, one POST and zero blocked writes; exact executed recipe must be supplied for provenance. New strengthened desktop version NOT RUN, do not rerun without separate CENTRAL authorization. See D03.md for integrated qualification and external evidence gates.
