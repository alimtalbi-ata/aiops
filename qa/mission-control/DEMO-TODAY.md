# P0 DEMO TODAY — AUTH02 baseline only
CENTRAL reports SIM01 PASS and local SIM02 Desktop 11/11 PASS, one POST, zero blocked writes. Do not replay. D versioned SIM02 successors NOT_RUN.

Use already qualified Debian Playwright dependencies, no network install, exact full checkout mounted. From qa/mission-control, with approved BASE_URL and privately supplied QA_VIEWER_TOKEN only, unset QA_OPERATOR_TOKEN QA_ENABLE_SIM02 QA_ENABLE_SIM02_MOBILE. Run `npm test -- smoke.spec.cjs --project=chromium --retries=0` then `QA_REQUIRE_VIEWER=1 npm test -- acme-readonly.spec.cjs acme-browser.spec.cjs --project=chromium --retries=0`. Select only named specs. AUTH02 operator is configured, so anonymous operator session expected 401 rather than original unconfigured 503: do not count original smoke assertion as regression; use viewer suite for P0 and record original smoke mismatch separately. No simulation, story or mutation clicks. Private reports only.

| Screen | Demo claim | New P0 status |
|---|---|---|
| Vue globale / Observabilité | technical health/history, business UNKNOWN | NOT_RUN |
| Services | technical inventory | NOT_RUN |
| Incidents / Twin | synthetic ACME, keyboard selection | NOT_RUN |
| Intelligence | synthetic Analyst/Critic | NOT_RUN |
| Automatisation | preview only, viewer simulation disabled | NOT_RUN |
| Evidence | synthetic checkpoints MISSING | NOT_RUN |
| ITSM | link only, no real ticket | NOT_RUN |
| Return operational | no synthetic incident | NOT_RUN |

CENTRAL record exact checkout, image digest, tool versions, exit code, pass/fail/blocked per screen, pre/post health 6/6 services and 7/7 targets, zero writes. Do not claim current receipt persistence or external audit. No baseline deploy. Mobile 320/360/390 remains separate RO candidate; full simulation NO-GO. D03 and DATA02 deferred for P0.
