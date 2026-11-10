# Host launch — authorized night 9–10 November 2026

Run from the host terminal, outside Codex's command sandbox. Existing checkouts and cron are not used. `start` detaches locally and refuses nested/expired contexts. The script resolves checkout/runtime from its own location.

```bash
python3 /tmp/aiops-night-20261109/checkout/docs/handoffs/integration/night-20261109/supervisor.py start
```

Check runtime/state.json plus `ps` for its supervisor_pid and child_pid before claiming active. Journal: runtime/supervisor.log; cycle JSONL and final reports remain under runtime beside the checkout. No secret log upload is automatic. The foreground process holds a fixed flock. Codex invocation uses `-a never exec --sandbox workspace-write -c sandbox_workspace_write.network_access=true` from host; no sandbox bypass. Commands require codex/gh/Git credentials already configured on that host.

```bash
python3 /tmp/aiops-night-20261109/checkout/docs/handoffs/integration/night-20261109/supervisor.py stop
```

Deadline: 2026-11-10T07:00:00+01:00, no start after expiry. Interval 600 seconds, cycle maximum 540 seconds. Local STOP request takes effect within the polling interval (0.2 s under normal scheduling). Supervisor termination kills the active group; independent GNU timeout bounds children if supervisor is forcibly killed. No systemd/cron installation. Keep this directory until reporting is complete.
