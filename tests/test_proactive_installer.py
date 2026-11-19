import os
import subprocess
from pathlib import Path


def test_installer_restores_original_crontab_after_partial_write_failure(tmp_path):
    fakebin=tmp_path/"bin"
    fakebin.mkdir()
    home=tmp_path/"home"
    home.mkdir()
    crontab=tmp_path/"crontab"
    original="* * * * * /usr/bin/keep-this-job\n17 * * * * /usr/bin/backup\n"
    crontab.write_text(original)

    commands={
      "id":"#!/bin/sh\necho aiops\n",
      "hostname":"#!/bin/sh\necho srv-deb-05\n",
      "flock":"#!/bin/sh\nexit 0\n",
      "gh":"#!/bin/sh\n# Return empty Python modules for the staged observer files.\nexit 0\n",
      "python3":"#!/bin/sh\nif [ \"$1\" = \"-m\" ]; then exit 0; fi\nmkdir -p \"$HOME/.local/state/aiops2-proactive\"\nprintf '{\\"state\\":\\"CI_PENDING\\",\\"deploy_authorized\\":false}' > \"$HOME/.local/state/aiops2-proactive/candidate.json\"\n",
      "crontab":"#!/bin/bash\nif [[ \"$1\" == \"-l\" ]]; then cat \"$FAKE_CRONTAB\"; exit 0; fi\ncount=0; [[ -f \"$FAKE_COUNT\" ]] && count=$(cat \"$FAKE_COUNT\"); count=$((count+1)); echo \"$count\" > \"$FAKE_COUNT\"\ncp \"$1\" \"$FAKE_CRONTAB\"\nif [[ \"$count\" == 1 ]]; then exit 42; fi\n"
    }
    for name,body in commands.items():
        path=fakebin/name
        path.write_text(body)
        path.chmod(0o755)

    env=os.environ.copy()
    env.update({
      "HOME":str(home),
      "FAKE_CRONTAB":str(crontab),
      "FAKE_COUNT":str(tmp_path/"crontab-count"),
      "PATH":f"{fakebin}:/usr/bin:/bin"
    })
    script=Path(__file__).resolve().parents[1]/"deploy/install-proactive-observer.sh"
    result=subprocess.run(["bash",str(script),"a"*40],env=env,text=True,capture_output=True,timeout=15)
    assert result.returncode==42,result.stderr
    assert crontab.read_text()==original
    assert "restored and verified" in result.stderr
    backups=list((home/".local/state/aiops2-proactive").glob("crontab.*"))
    assert len(backups)==1
    assert backups[0].read_text()==original
