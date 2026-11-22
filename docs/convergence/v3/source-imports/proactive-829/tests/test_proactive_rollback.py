import os
import subprocess
from pathlib import Path


def test_rollback_removes_only_tagged_cron_entries(tmp_path):
    fakebin=tmp_path/"bin"
    fakebin.mkdir()
    home=tmp_path/"home"
    home.mkdir()
    crontab=tmp_path/"crontab"
    original="* * * * * /usr/bin/keep-this-job\n*/5 * * * * /usr/bin/python3 observer.py # AIOPS2_PROACTIVE_OBSERVER_V1\n17 * * * * /usr/bin/backup\n"
    crontab.write_text(original)

    commands={
      "id":"#!/bin/sh\necho aiops\n",
      "hostname":"#!/bin/sh\necho srv-deb-05\n",
      "flock":"#!/bin/sh\nexit 0\n",
      "crontab":"#!/bin/sh\nif [ \"$1\" = \"-l\" ]; then cat \"$FAKE_CRONTAB\"; else cp \"$1\" \"$FAKE_CRONTAB\"; fi\n"
    }
    for name,body in commands.items():
        path=fakebin/name
        path.write_text(body)
        path.chmod(0o755)

    env=os.environ.copy()
    env.update({"HOME":str(home),"FAKE_CRONTAB":str(crontab),"PATH":f"{fakebin}:/usr/bin:/bin"})
    script=Path(__file__).resolve().parents[1]/"deploy/rollback-proactive-observer.sh"
    result=subprocess.run(["bash",str(script)],env=env,text=True,capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
    assert crontab.read_text()=="* * * * * /usr/bin/keep-this-job\n17 * * * * /usr/bin/backup\n"
    backups=list((home/".local/state/aiops2-proactive").glob("crontab-before-rollback.*"))
    assert len(backups)==1
    assert backups[0].read_text()==original
