// Host-side opt-in wiring for the existing filesystem DEMO panel.
// Import this module only from the authorized Portal demo bundle.
// Never replace the existing demo until the backend GET contract is deployed.
import {mountFsV28} from './fs-v28-host-hook.mjs';

export function connectFilesystemDemo(root, {authorized=false}={}) {
  if (!authorized) throw new Error('AUTHORIZED_DEMO_CONTEXT_REQUIRED');
  if (!root || typeof root.querySelector !== 'function') throw new TypeError('DEMO_ROOT_REQUIRED');
  const required = ['incident','run','evidence','core','temporal','policy','source','safety'];
  for (const key of required) {
    if (!root.querySelector('[data-fs-v28="'+key+'"]')) throw new Error('MISSING_FS_V28_SLOT:'+key);
  }
  const view = mountFsV28(root);
  return Object.freeze({
    refresh: () => view.refresh(),
    dispose: () => view.dispose()
  });
}
