# FS1113 — Historical chart request race

Date: 2026-11-07  
Branch: `feat/portal-7777-observability-cmdb`  
Scope: non-production portal candidate only.

## Evidence and diagnosis

The FS1108/FS1109 candidate diagnostics returned HTTP 200 for the visual page and both same-origin history APIs (`availability`, `scrape_duration`). The API returned five series and 305 points for 1h; the 6h result returned five series and 1,205 points.

FS1112 then passed the initial desktop view and the 1h matrix row, but failed after changing to 6h: the legend had ten direct child entries while the API still returned five series. This is consistent with overlapping asynchronous history loads: metric and window controls can start multiple requests, and an older response can append after a newer render has cleared the legend.

## Correction

`scripts/fs/fs1097_patch.py` now:
- assigns a monotonically increasing request generation to every history load;
- aborts the previous request with `AbortController`;
- passes the abort signal to `fetch`;
- ignores stale responses and stale errors;
- allows only the latest request to re-enable the refresh control.

The UI remains same-origin, read-only, bounded to the fixed metric/window contract, and uses CSP hashes recomputed from the final inline script/style.

## Regression gate

`scripts/fs/FS.1097-build-history-chart-candidate.sh` asserts the stale-request guard exists in the generated UI and retains import, route, CSP and ASGI checks.

Run `bash scripts/fs/FS.1113-history-race-candidate-validation.sh` to force a fresh candidate image build and execute the full FS1107 publish-first network lifecycle and Chromium matrix:
- metrics: `availability`, `scrape_duration`;
- windows: `1h`, `6h`, `24h`;
- refresh and mobile viewport;
- console, page, request and HTTP error checks.

## Docker rootless lifecycle

Do not publish a container directly on an internal bridge. FS1106/FS1107 verified that the candidate must be created on `aiops2-rebuild-public` with explicit host publish, then attached to `aiops2-rebuild-control`, `aiops2-rebuild-integration`, and `aiops2-rebuild-observability`. Runtime port binding and host HTTP 200 remained stable at each stage.

## Safety and promotion

Production image observed: `aiops2-portal:fs1073-csp-candidate`. The FS1113 gate asserts this image before and after the candidate run. It never deploys or mutates production. Do not promote until the complete browser matrix reports PASS and the operator separately authorizes deployment.

## Result status

The code correction and gate assertions are committed. The Debian candidate rebuild and full Chromium rerun are **pending operator execution**; no runtime PASS is claimed by this document.
