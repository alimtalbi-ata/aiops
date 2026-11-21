# Portal convergence — build contract

The portal Dockerfile keeps the `app` context and declares a named `noc_scripts` context from repository `scripts/`. Only the five computed NOC Python modules are copied to `/scripts`, matching the existing route import path. No runtime credentials belong in build arguments.

From the repository root, use `docker build --build-context noc_scripts=./scripts --file app/portal/Dockerfile --tag aiops2-portal-demo-smoke:ci app` in an authorized disposable CI environment. Compose uses `additional_contexts` (Compose 2.17+ and a compatible BuildKit builder). The existing install and big-bang scripts invoke Compose and inherit this configuration; do not execute them for qualification. The deployment archive includes repository scripts. The existing preflight checks Compose configuration but does not attest builder support.

Do not use an old standalone `docker build -f app/portal/Dockerfile app` invocation. No deployment permission or Debian compatibility is implied. Require successful isolated image smoke, full CI and browser qualification before promotion.
