import datetime as dt
import json
from pathlib import Path
from unittest.mock import patch

import proactive_watchdog as watchdog
import proactive_build_handoff as handoff


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def test_watchdog_publishes_fresh_observation_once(tmp_path):
    root = tmp_path / ".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha = "a" * 40
    (root / "candidate.json").write_text(json.dumps({
        "observed_at": utc_now(), "state": "BUILD_ELIGIBLE",
        "sha": sha, "deploy_authorized": False
    }))
    with patch.object(watchdog.Path, "home", return_value=tmp_path), patch.object(
        watchdog.subprocess, "run"
    ) as run:
        watchdog.main()
        watchdog.main()
    assert run.call_count == 1
    receipts = list(root.glob("reported-*.json"))
    assert len(receipts) == 1
    assert json.loads(receipts[0].read_text())["status"] == "PUBLISHED"


def test_watchdog_fails_closed_on_stale_observation(tmp_path):
    root = tmp_path / ".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=10)).isoformat()
    (root / "candidate.json").write_text(json.dumps({
        "observed_at": old, "state": "BUILD_ELIGIBLE",
        "sha": "a" * 40, "deploy_authorized": False
    }))
    with patch.object(watchdog.Path, "home", return_value=tmp_path), patch.object(
        watchdog.subprocess, "run"
    ) as run:
        watchdog.main()
    assert run.call_count == 1
    args = run.call_args.args[0]
    assert "DISCOVERY_STALE" in args[-1]


def test_handoff_publishes_only_fresh_eligible_candidate(tmp_path):
    root = tmp_path / ".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha = "b" * 40
    (root / "candidate.json").write_text(json.dumps({
        "observed_at": utc_now(), "state": "BUILD_ELIGIBLE",
        "sha": sha, "pr": 818, "deploy_authorized": False
    }))
    with patch.object(handoff.Path, "home", return_value=tmp_path), patch.object(
        handoff.subprocess, "run"
    ) as run:
        handoff.main()
    assert run.call_count == 1
    receipt = json.loads((root / f"build-handoff-{sha}.json").read_text())
    assert receipt["status"] == "PUBLISHED"


def test_handoff_marks_uncertain_publication_without_blind_retry(tmp_path):
    root = tmp_path / ".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha = "c" * 40
    (root / "candidate.json").write_text(json.dumps({
        "observed_at": utc_now(), "state": "BUILD_ELIGIBLE",
        "sha": sha, "pr": 818, "deploy_authorized": False
    }))
    with patch.object(handoff.Path, "home", return_value=tmp_path), patch.object(
        handoff.subprocess, "run", side_effect=OSError("network uncertain")
    ) as run:
        try:
            handoff.main()
        except OSError:
            pass
        else:
            raise AssertionError("expected uncertain publication error")
        handoff.main()
    assert run.call_count == 1
    receipt = json.loads((root / f"build-handoff-{sha}.json").read_text())
    assert receipt["status"] == "PUBLICATION_UNCERTAIN"
