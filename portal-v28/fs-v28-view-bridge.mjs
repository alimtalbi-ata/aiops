// Browser-only view bridge for the V28 filesystem panel. Never mutates services.
import {IDS, load, unavailable} from "./fs-v28-readonly-adapter.mjs";
const FIELDS = ["incident","core","temporal","policy","evidence"];
const refreshEpoch = new WeakMap();
export function renderFsV28(root, value) {
  if (!root || typeof root.querySelector !== "function") throw new TypeError("root required");
  const v = value && value.synthetic === true && value.noLiveEffects === true && value.ids?.incident === IDS.incident && value.ids?.run === IDS.run && value.ids?.evidence === IDS.evidence
    ? value : unavailable("INVALID_PROJECTION");
  const write = (name, text) => {
    const node = root.querySelector('[data-fs-v28="'+name+'"]');
    if (node) node.textContent = String(text);
  };
  write("incident-id", IDS.incident);
  write("run-id", IDS.run);
  write("evidence-id", IDS.evidence);
  write("mode", "SYNTHETIC");
  write("effects", "NO_LIVE_EFFECTS");
  write("source", v.source === "CORE_EVIDENCE_READONLY" ? "CORE_EVIDENCE_READONLY" : "UNAVAILABLE");
  for (const field of FIELDS) write(field, v.source === "CORE_EVIDENCE_READONLY" ? v[field] ?? "UNKNOWN" : "UNKNOWN");
  write("approval", "NOT_ATTESTED");
  write("resolution", "NOT_ATTESTED");
  write("availability", v.source === "CORE_EVIDENCE_READONLY" ? "READONLY_CONNECTED" : "UNAVAILABLE");
  write("reason", v.reason || "");
  return v;
}
// Call only from the existing authorized DEMO view; no OIDC bypass or API fallback.
export async function refreshFsV28(root, options={}) {
  if (!root || (typeof root !== "object" && typeof root !== "function")) throw new TypeError("root required");
  const epoch = (refreshEpoch.get(root) || 0) + 1;
  refreshEpoch.set(root, epoch);
  renderFsV28(root, unavailable("LOADING"));
  const v = await load(options);
  // A delayed response must not overwrite a newer authorization or service result.
  if (refreshEpoch.get(root) !== epoch) return unavailable("SUPERSEDED_REFRESH");
  return renderFsV28(root, v);
}

// Invalidate pending refreshes on logout/navigation, even when fetch ignores abort.
export function invalidateFsV28(root, reason="VIEW_DISPOSED") {
  refreshEpoch.set(root, (refreshEpoch.get(root) || 0) + 1);
  return renderFsV28(root, unavailable(reason));
}
