# AIOPS2 — handover différentiel 2026-11-11 17:11 CET

Branch-only handover; coordinate ownership with #555 and concurrent Drafts (#599/#618/#625/#632), do not overwrite canonical documentation.

- New audit: `docs/audits/AIOPS2-RUN-STATUS-UNVERIFIED-20261111-1711.md`, U-017 negative browser fixture protocol (specified, NOT EXECUTED).
- Source `app/portal/portal_bootstrap_client.js` blob `ac58f73c725f5e088081bffed4478ea18585ef5c`: Run status strings rendered without row-level unverified qualification; envelope still marked READABLE_UNVERIFIED. Risk is ambiguous row-level LIVE presentation, not confirmed deployed regression.
- v28/V145, :7777/:17778 and E2E remain UNKNOWN/NOT VERIFIED. No host freshness check. #557 rootful/rootless false diagnostic per operator, no recovery work.
- CI must be checked at this exact branch SHA; rollback close Draft or revert branch-only documentation; no merge/deploy/ACL/HITL changes.
