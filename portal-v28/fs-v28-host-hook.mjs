// Opt-in integration for the existing authorized filesystem DEMO panel.
// No polling, navigation, service mutation, or private API access.
import {refreshFsV28, renderFsV28, invalidateFsV28} from './fs-v28-view-bridge.mjs';
import {unavailable} from './fs-v28-readonly-adapter.mjs';
const active = new WeakMap();
export function mountFsV28(root, options={}) {
  if (!root || typeof root.querySelector !== 'function') throw new TypeError('authorized DEMO root required');
  if (active.has(root)) return active.get(root);
  let disposed = false;
  let controller = null;
  renderFsV28(root, unavailable('AWAITING_AUTHORIZED_READ'));
  const handle = {
    async refresh() {
      if (disposed) return unavailable('DISPOSED');
      controller?.abort();
      controller = new AbortController();
      return refreshFsV28(root, {...options, signal:controller.signal});
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      controller?.abort();
      // Clear stale data and invalidate even a fetch implementation ignoring abort.
      invalidateFsV28(root, 'VIEW_DISPOSED');
      active.delete(root);
    }
  };
  active.set(root, handle);
  return handle;
}
