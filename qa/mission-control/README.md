# D01 runtime smoke FIX01
Run on approved test checkout, not production image. Node 22. From qa/mission-control:
```sh
umask 077
npm install --package-lock-only --ignore-scripts
npm ci
npx playwright install chromium
BASE_URL='<approved origin>' UI_PATH='/mission-control' npm test
```
Lock generation is provisional until reviewed and committed. UI_PATH must be confirmed by CENTRAL. No secrets for this suite; no authenticated tests, no simulation POST. Browser blocks non-read methods. Reports/traces may contain sensitive server data: keep private, never publish raw artifacts. This suite is runtime only; no mocks and no runtime PASS claimed.
For isolated A/B/C tests use assembled checkout including C test overlay 8144ebc9252d540a3ecd23acbb01007314015414. From root with isolated venv and build-aligned dependencies:
```sh
PYTHONPATH=app python -m pytest tests/mission_data tests/mission_actions -v
cd frontend/mission-control
OUT=$(mktemp -d)
./node_modules/.bin/tsc --strict --target ES2020 --module commonjs --outDir "$OUT" src/ux/operational.test.ts src/ux/analytics.test.ts && node "$OUT/operational.test.js" && node "$OUT/analytics.test.js"
OUT=$(mktemp -d)
./node_modules/.bin/tsc --strict --skipLibCheck --target ES2022 --module commonjs --lib ES2022,DOM --outDir "$OUT" src/actions/providers.test.ts && node -e 'require(process.argv[1]).verifyProviderContracts().catch(e=>{console.error(e);process.exitCode=1})' "$OUT/providers.test.js"
```
No production secrets or network for unit tests. ACME official fixture required. P1 authenticated API cross-contract test is implemented; browser journey and P2 simulation are not yet implemented.

## ACME viewer read-only
Set QA_VIEWER_TOKEN through an approved local secret mechanism, never on a command line or in Git. Run `npm test -- acme-readonly.spec.cjs` with BASE_URL HTTPS or loopback only. No redirects, no traces/screenshots/video for this authenticated API test. Keep all reports private; sanitize before sharing. Missing viewer skips the test, not PASS. No POST or execution. The API checks synthetic classification, incident/run/source binding, affected CI IDs, missing evidence, LIVE ACL refusal. Remove token from environment after testing.
