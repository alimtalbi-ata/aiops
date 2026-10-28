# P0 — Copilot browser RBAC and response boundary (2026-10-28)

## Contract

`POST /api/copilot` is now **read-only** and requires `Authorization: Bearer <viewer-or-operator-token>`. A viewer token is mandatory for enabling the endpoint. Operator token is optional but must differ from viewer and internal tokens. Both are provisioned separately in new `.env` files; existing installations must manually configure their `.env` without exposing secrets. `compose.yml` passes these values only to the portal container.

Input is limited to `{"question": "<nonempty string up to 2048 chars>"}`; caller-supplied mode, tool definitions, Run mutation and unknown fields are refused (422). Authentication failures return 401; weak/missing/ambiguous credential configuration returns 503. No upstream request occurs in either case. Valid requests call the existing real Copilot service, which itself reads Core/Twin/Evidence APIs. The portal projects only the bounded `answer`, `question`, `sources`, `confidence`, `limitations` fields. Any malformed or mismatched upstream result returns `UNKNOWN` / 503 without leaking exception details. The response adds `READABLE_UNVERIFIED`, `runtime_authenticated=false`, `live_remediation_authorized=false`, and `UNATTESTED_UPSTREAM_API_READ`.

The browser clears its one-shot token input before making the request, uses `no-store`, and renders response text via `textContent`. It does not store tokens in localStorage or URL. This does **not** establish session management, a complete portal RBAC perimeter, NIM inference, or actual runtime evidence. Legacy home, bootstrap, components and other routes remain publicly accessible and require a separate global authentication design.

## CI and deployment

`tests/test_portal_copilot_auth.py` is an in-process HTTP contract suite using a patched upstream call. It is **not** integration evidence and does not contact NVIDIA NGX, Ollama, Debian or the public portal. `.github/workflows/quality.yml` runs it alongside existing tests and Compose validation. Real ephemeral service integration remains NOT_TESTED until a dedicated isolated environment is available.

Rollback: revert the portal guard, UI, and Compose/template changes as one code change; do not reuse internal service credentials for browser authentication. For an existing `.env`, generate two distinct 32-byte-or-longer random tokens and restart only after a separate approved preflight and backup. This PR does not deploy or change any running service.
