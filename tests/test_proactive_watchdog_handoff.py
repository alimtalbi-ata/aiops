import datetime as dt
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import proactive_watchdog as watchdog
import proactive_build_handoff as handoff


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def gh_pr(sha):
    return json.dumps({"state":"open","head":{"sha":sha,"repo":{"full_name":"alimtalbi-ata/aiops"}}})


def completed_pages(items):
    return subprocess.CompletedProcess(["gh","api"],0,json.dumps([items]),"")


def test_watchdog_publishes_fresh_observation_once(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="a"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"BUILD_ELIGIBLE","sha":sha,"deploy_authorized":False}))
    with patch.object(watchdog.Path,"home",return_value=tmp_path),patch.object(watchdog.subprocess,"run",return_value=subprocess.CompletedProcess(["gh","api"],0,json.dumps({"id":101,"user":{"login":"alimtalbi-ata"}}),"")) as run:
        watchdog.main()
        watchdog.main()
    assert run.call_count==1
    receipt=list(root.glob("reported-*.json"))
    assert len(receipt)==1
    assert json.loads(receipt[0].read_text())["status"]=="PUBLISHED"


def test_watchdog_skips_while_shared_discovery_lock_is_held(tmp_path):
    import fcntl
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    (root/"candidate.json").write_text(json.dumps({"state":"CHECKING","observed_at":utc_now(),"deploy_authorized":False}))
    with (root/"lock").open("a") as held:
        fcntl.flock(held,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with patch.object(watchdog.Path,"home",return_value=tmp_path),patch.object(watchdog.subprocess,"run") as run:
            watchdog.main()
        assert run.call_count==0


def test_watchdog_fails_closed_on_stale_or_future_observation(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    for stamp in [(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=10)).isoformat(),(dt.datetime.now(dt.timezone.utc)+dt.timedelta(minutes=2)).isoformat()]:
        for receipt in root.glob("reported-*.json"):
            receipt.unlink()
        (root/"candidate.json").write_text(json.dumps({"observed_at":stamp,"state":"BUILD_ELIGIBLE","sha":"a"*40,"deploy_authorized":False}))
        with patch.object(watchdog.Path,"home",return_value=tmp_path),patch.object(watchdog.subprocess,"run",return_value=subprocess.CompletedProcess(["gh","api"],0,json.dumps({"id":103,"user":{"login":"alimtalbi-ata"}}),"")) as run:
            watchdog.main()
        assert run.call_count==1
        assert "DISCOVERY_STALE" in run.call_args.args[0][-1]


def test_watchdog_reconciles_uncertain_publication_one_expected_author(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="d"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"CI_PENDING","sha":sha,"deploy_authorized":False}))
    marker_id=__import__("hashlib").sha256(f"CI_PENDING:{sha}".encode()).hexdigest()[:24]
    marker=f"[AIOPS2-WATCHDOG:{marker_id}]"
    receipt=root/f"reported-{marker_id}.json"
    receipt.write_text(json.dumps({"status":"PUBLICATION_UNCERTAIN","marker":marker}))
    with patch.object(watchdog.Path,"home",return_value=tmp_path),patch.object(watchdog.subprocess,"run",return_value=completed_pages([{"id":44,"body":marker+"\nbody","user":{"login":"alimtalbi-ata"}}])) as run:
        watchdog.main()
    assert run.call_count==1
    assert json.loads(receipt.read_text())["status"]=="PUBLISHED"


def test_watchdog_marks_multiple_matches_for_escalation(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="e"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"CI_PENDING","sha":sha,"deploy_authorized":False}))
    marker_id=__import__("hashlib").sha256(f"CI_PENDING:{sha}".encode()).hexdigest()[:24]
    marker=f"[AIOPS2-WATCHDOG:{marker_id}]"
    receipt=root/f"reported-{marker_id}.json"
    receipt.write_text(json.dumps({"status":"STARTED","marker":marker}))
    items=[{"id":1,"body":marker,"user":{"login":"alimtalbi-ata"}},{"id":2,"body":marker,"user":{"login":"alimtalbi-ata"}}]
    with patch.object(watchdog.Path,"home",return_value=tmp_path),patch.object(watchdog.subprocess,"run",return_value=completed_pages(items)):
        watchdog.main()
    assert json.loads(receipt.read_text())["status"]=="DUPLICATE_ESCALATION"


def test_watchdog_wrong_author_is_not_accepted(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="f"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"CI_PENDING","sha":sha,"deploy_authorized":False}))
    marker_id=__import__("hashlib").sha256(f"CI_PENDING:{sha}".encode()).hexdigest()[:24]
    marker=f"[AIOPS2-WATCHDOG:{marker_id}]"
    receipt=root/f"reported-{marker_id}.json"
    receipt.write_text(json.dumps({"status":"STARTED","marker":marker}))
    with patch.object(watchdog.Path,"home",return_value=tmp_path),patch.object(watchdog.subprocess,"run",return_value=completed_pages([{"id":2,"body":marker,"user":{"login":"someone-else"}}])):
        watchdog.main()
    assert json.loads(receipt.read_text())["status"]=="AUTHOR_CONFLICT"


def test_handoff_publishes_only_fresh_eligible_candidate_and_rechecks_head(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="b"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"BUILD_ELIGIBLE","sha":sha,"pr":818,"deploy_authorized":False}))
    with patch.object(handoff.Path,"home",return_value=tmp_path),patch.object(handoff.subprocess,"check_output",return_value=gh_pr(sha)),patch.object(handoff.subprocess,"run",return_value=subprocess.CompletedProcess(["gh","api"],0,json.dumps({"id":102,"user":{"login":"alimtalbi-ata"}}),"")) as run:
        handoff.main()
    assert run.call_count==1
    assert json.loads((root/f"build-handoff-{sha}.json").read_text())["status"]=="PUBLISHED"


def test_handoff_rejects_sha_changed_before_publication(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="b"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"BUILD_ELIGIBLE","sha":sha,"pr":818,"deploy_authorized":False}))
    with patch.object(handoff.Path,"home",return_value=tmp_path),patch.object(handoff.subprocess,"check_output",return_value=gh_pr("c"*40)),patch.object(handoff.subprocess,"run") as run:
        handoff.main()
    assert run.call_count==0
    assert json.loads((root/f"build-handoff-{sha}.json").read_text())["status"]=="OBSOLETE_SHA"


def test_handoff_reconciles_uncertain_marker_without_blind_repost(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="c"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"BUILD_ELIGIBLE","sha":sha,"pr":818,"deploy_authorized":False}))
    marker=f"[CENTRAL][BUILD_QUALIFICATION:{sha}]"
    receipt=root/f"build-handoff-{sha}.json"
    receipt.write_text(json.dumps({"status":"PUBLICATION_UNCERTAIN","sha":sha,"marker":marker}))
    with patch.object(handoff.Path,"home",return_value=tmp_path),patch.object(handoff.subprocess,"run",return_value=completed_pages([{"id":88,"body":marker+"\nbody","user":{"login":"alimtalbi-ata"}}])) as run:
        handoff.main()
    assert run.call_count==1
    assert run.call_args.args[0][:2]==["gh","api"]
    assert json.loads(receipt.read_text())["status"]=="PUBLISHED"


def test_watchdog_escalates_after_three_complete_zero_match_scans(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="9"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"CI_PENDING","sha":sha,"deploy_authorized":False}))
    marker_id=__import__("hashlib").sha256(f"CI_PENDING:{sha}".encode()).hexdigest()[:24]
    receipt=root/f"reported-{marker_id}.json"
    receipt.write_text(json.dumps({"status":"PUBLICATION_UNCERTAIN","marker":f"[AIOPS2-WATCHDOG:{marker_id}]"}))
    with patch.object(watchdog.Path,"home",return_value=tmp_path),patch.object(watchdog.subprocess,"run",return_value=completed_pages([])) as run:
        watchdog.main()
        watchdog.main()
        watchdog.main()
    assert run.call_count==3
    assert json.loads(receipt.read_text())["status"]=="MANUAL_ESCALATION_REQUIRED"


def test_handoff_rechecks_head_after_reservation_before_post(tmp_path):
    root=tmp_path/".local/state/aiops2-proactive"
    root.mkdir(parents=True)
    sha="8"*40
    (root/"candidate.json").write_text(json.dumps({"observed_at":utc_now(),"state":"BUILD_ELIGIBLE","sha":sha,"pr":818,"deploy_authorized":False}))
    with patch.object(handoff.Path,"home",return_value=tmp_path),patch.object(handoff.subprocess,"check_output",side_effect=[gh_pr(sha),gh_pr("7"*40)]),patch.object(handoff.subprocess,"run") as run:
        handoff.main()
    assert run.call_count==0
    assert json.loads((root/f"build-handoff-{sha}.json").read_text())["status"]=="OBSOLETE_SHA"
