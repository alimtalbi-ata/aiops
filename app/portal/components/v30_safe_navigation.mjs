/**
 * V30 six-domain navigation candidate. Presentation only: no network, actions or
 * claim of operational readiness. Integrators must supply independently verified
 * server-side identity, tenant ACL and connector attestations.
 */
export const V30_SECTIONS = Object.freeze([
  ["command-center", "Command Center"],
  ["observability", "Observability"],
  ["incident-itsm", "Incident / ITSM"],
  ["ai-decision", "AI Decision"],
  ["operations-control", "Operations Control"],
  ["demo-center", "DemoCenter"],
]);

const escapeHTML = (value) => String(value).replace(/[&<>"']/g, (char) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
})[char]);

/** Never infer LIVE from a URL, caller-provided mode or populated demo fixture. */
export function resolveV30Presentation({ mode, liveAttested = false, tenantAuthorized = false } = {}) {
  if (mode === "DEMO") return Object.freeze({ mode: "DEMO", trust: "SYNTHETIC", live: false });
  if (mode === "REPLAY") return Object.freeze({ mode: "REPLAY", trust: "HISTORICAL", live: false });
  // Presentation-only inputs cannot establish server-side attestation or tenant ACL.
  // Until a trusted server contract is integrated, LIVE always fails closed.
  return Object.freeze({ mode: "UNKNOWN", trust: "UNVERIFIED", live: false });
}

/**
 * Accessible, responsive-ready semantic navigation markup.
 * This component does not render live data, issue commands or grant access.
 * Paths are internal anchors only, not routes to assume deployed.
 */
export function renderV30Navigation({ mode, liveAttested, tenantAuthorized, active = "command-center" } = {}) {
  const state = resolveV30Presentation({ mode, liveAttested, tenantAuthorized });
  const items = V30_SECTIONS.map(([slug, title]) => {
    const selected = active === slug ? ' aria-current="page"' : "";
    return `<li><a href="#v30-${slug}"${selected}>${escapeHTML(title)}</a></li>`;
  }).join("");
  return `<nav class="v30-nav" aria-label="Espaces V30" data-mode="${state.mode}" data-trust="${state.trust}" data-live="${state.live}"><p class="v30-mode" role="status">Mode : ${state.mode} — ${state.trust}</p><ul class="v30-nav-list">${items}</ul></nav>`;
}
