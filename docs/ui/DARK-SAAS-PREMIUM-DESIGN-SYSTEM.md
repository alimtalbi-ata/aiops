# AIOps 2.0 — Dark SaaS Premium UI system

**Status:** implementation increment / DEV only  
**Branch:** `feat/ui-dark-saas-premium-20261117`

## Intent

Give every first-party Portal screen and provisioned Grafana dashboard one coherent visual language. This is a presentation-only change: it must not change authentication, tenant authorization, source provenance, read/write behavior, or the fail-closed UNKNOWN states.

## Visual tokens

| Token | Value | Use |
|---|---|---|
| Background | `#080B14` | Midnight canvas |
| Surface | `#111827` | Primary cards and panels |
| Raised surface | `#172136` | Elevated panels and navigation |
| Border | `#293650` | Quiet separators |
| Text | `#F4F7FF` | Primary content |
| Muted | `#9AA8C7` | Secondary content |
| Electric violet | `#8B5CF6` | Primary brand accent |
| Electric blue | `#38BDF8` | Secondary accent / links |
| Success | `#34D399` | Explicit positive state |
| Warning | `#FBBF24` | Attention / UNKNOWN context |
| Critical | `#FB7185` | Critical state |

## Components and behavior

- Shared local stylesheet: `app/portal/aiops_theme.css`.
- Portal middleware adds the stylesheet to HTML responses only and extends the existing CSP with `style-src 'self'`; API payloads and non-HTML responses are not rewritten.
- Shared styling covers the Command Center, Run/Incident journey, ACME Impact, Explore/Story, and GLPI/ITSM HTML surfaces.
- Responsive layouts, visible keyboard focus, reduced-motion handling, and no remote fonts/assets are part of the baseline.
- Grafana's provisioned ACME Command Center and AIOps Observability Control Plane dashboards declare dark mode and a six-hour default view. Compose sets `GF_USERS_DEFAULT_THEME=dark` for the native Grafana chrome. Prometheus scrapes itself and Alertmanager to expose operational metrics to the branded Grafana dashboard.
- GLPI 11 receives a scoped custom SCSS palette at `config/glpi/themes/aiops-premium.scss`, mounted read-only into its documented custom palette directory. An authorized GLPI administrator must select/force the palette for the intended user/entity scope.
- n8n supports a per-user dark theme preference; managed operator accounts must select it in Personal settings. There is no server-wide branded CSS override in this patch.

## Safety and trust boundaries

- No auth, tenant ACL, RBAC, token, API, or business logic changes.
- UNKNOWN, SYNTHETIC, NOT_TESTED, and NOT_ATTESTED labels remain explicit; styling must never imply health or qualification.
- No external CSS/CDN, analytics, browser storage, or additional network calls.
- The Portal stylesheet is a local static asset served with `no-store` and `nosniff`.

## Acceptance

1. The local stylesheet endpoint returns CSS with violet and blue design tokens.
2. Every representative Portal HTML surface links the shared stylesheet.
3. Existing CSP retains `default-src 'none'` and `frame-ancestors 'none'`; `style-src 'self'` is added without relaxing script/connect permissions.
4. API responses are not HTML-rewritten.
5. Existing Portal security, read-model, and synthetic-only tests remain green.
6. Grafana dashboard JSON remains valid and uses `style: dark`.

## Scope still to audit

This increment themes all first-party Portal HTML routes, the provisioned ACME Grafana dashboard and (through supported configuration) Grafana's default native theme plus a GLPI 11 custom palette. n8n dark mode is a per-user preference and needs operator-level selection. Prometheus and Alertmanager native consoles have no supported brand-theme setting in the deployed config; keep them as native diagnostic tools and use the Portal/Grafana as the branded operations surfaces. No live external instance was modified or visually verified.

## Convergence B adapter contract (proposed, not integrated)

Source shell: Golden/#805 `app/portal/ui_theme.py`, blob `fcc604e5d62a263157e7d240318c51890f5688e2`. Preserve shell(), panel(), table(), pretty(), escaping, mode disclosure and current-page semantics. Do not copy the Golden navigation blindly: resolve each route against the selected Convergence host.

Map existing shell tokens to the Premium palette: --bg to --ai-bg, --card to --ai-surface, --text to --ai-text, --muted to --ai-muted, --line to --ai-border, --hero to --ai-bg-soft, --c to --ai-violet. Use --ai-blue for links and keyboard focus. Dark is the default regardless of OS preference; remove the light-theme toggle only when its script and control can be removed together. Preserve status-specific colors and simulation disclaimers.

Use one local stylesheet and explicit template integration; do not widen CSP to enable the old inline toggle. Avoid generic header/card overrides on semantic timeline content. Verify navigation targets, keyboard access, table overflow and 320/768/1440px layouts in a real browser. No new business routes or demo orchestrator. This adapter contract is a review candidate, not a qualified implementation.
