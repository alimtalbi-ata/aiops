# AIOps 2.0 — External service UI convergence

**Branch:** `feat/ui-dark-saas-premium-20261117`  
**Mode:** DEV configuration only; no running service was changed.

## Shared visual contract

Use the same palette wherever the product exposes a supported theme surface:

| Token | Value |
|---|---|
| Midnight background | `#080B14` |
| Slate surface | `#111827` |
| Raised surface | `#172136` |
| Border | `#293650` |
| Primary text | `#F4F7FF` |
| Muted text | `#9AA8C7` |
| Electric violet | `#8B5CF6` |
| Electric blue | `#38BDF8` |

## Supported configuration implemented

### Grafana

- Compose sets `GF_USERS_DEFAULT_THEME=dark`, so users without a higher-priority personal/team preference receive dark UI.
- The ACME Command Center dashboard remains provisioned in dark mode.
- Grafana user preferences can override the server default; validate/standardize org and personal preferences during rollout.
- Grafana's native chrome uses Grafana's supported dark theme. The violet/blue brand accents are guaranteed in the provisioned dashboards and AIOps Portal, not a wholesale replacement of Grafana's internal component CSS.
- A new **AIOps Observability Control Plane** dashboard presents Prometheus and Alertmanager scrape health, active-alert metric, Prometheus head-series count, rule-evaluation rate and failed-notification rate. Prometheus now scrapes its own metrics and Alertmanager. Missing metric series remain missing/UNKNOWN; do not interpret absence as zero.

### GLPI 11

- Custom SCSS palette: `config/glpi/themes/aiops-premium.scss`.
- Compose mounts `config/glpi/themes` read-only at `/var/glpi/files/_themes`, matching the official image's `GLPI_VAR_DIR=/var/glpi/files` and GLPI 11 custom-palette discovery path.
- Palette includes `$is-dark: true`, a palette-scoped root selector, brand accents, and the four static swatches required for the palette picker.
- After deployment, an authorized GLPI administrator must select **AIOps Premium** under **Tools → Custom palettes**, then set the intended default/forced palette using the GLPI 11 administration controls. Personal preferences and entity-level palette settings can otherwise take precedence.
- Do not edit GLPI database preferences directly or bypass entity/profile authorization.

## Native UI preferences / limitations

### n8n 2.40.6

n8n exposes a per-user theme preference under **Settings → Personal → Personalisation → Theme → Dark**. This is a user preference, not a supported server-wide branding override. Set it for each managed operator account; do not inject CSS into the editor bundle or patch vendor assets.

### Prometheus and Alertmanager

Their bundled native consoles do not expose a supported brand-theme/palette setting in the deployed configuration. Do not patch vendor HTML/JS or use brittle reverse-proxy CSS injection. Keep them reachable for native diagnostics, but use the AIOps Portal and the new Grafana **AIOps Observability Control Plane** dashboard as the branded operational surfaces. The dashboard reads their metrics through Prometheus; it does not replace the native admin consoles or their auth/authorization boundaries.

## Deployment / acceptance checklist

1. Review this branch and PR; do not apply changes to a live host from CI.
2. Validate the Compose configuration with the target deployment's generated secrets.
3. Recreate/restart only Grafana and GLPI in a controlled DEV window after approval; verify Grafana's server default and GLPI's palette discovery.
4. In GLPI 11, select/force the custom palette for the intended entity/user scope.
5. Set dark theme in each managed n8n operator account.
6. Verify Prometheus scrapes itself and Alertmanager, and verify the new Grafana observability dashboard renders actual metric series; missing series remain UNKNOWN rather than being fabricated.
7. Verify Prometheus and Alertmanager remain functional; their native themes are intentionally not overridden.
8. Capture screenshots of Portal, Grafana, GLPI and n8n at desktop and mobile widths; record any unsupported UI surfaces as exceptions.
9. Confirm no auth, role, tenant, ticket, Run, workflow, alert, datasource or API behavior changed.

## Scope / truthfulness

This is a configuration and asset increment, not proof of a live visual deployment. Prometheus and Alertmanager cannot be truthfully claimed to use the branded palette. n8n requires per-user preference changes. GLPI requires an administrator to select/force the palette. No production or SRV-DEB-05 operation was performed.
