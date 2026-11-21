import os
import subprocess
from pathlib import Path


def test_installer_restores_original_crontab_after_partial_write_failure(tmp_path):
    fakebin=tmp_path/"bin"
    fakebin.mkdir()
    home=tmp_path/"home"
    home.mkdir()
    crontab=tmp_path/"crontab"
    original="* * * * * /usr/bin/keep-this-job\\n17 * * * * /usr/bin/backup\\n"
    crontab.write_text(original)

    commands={
      "id":"""#!/bin/sh
echo aiops
""",
      "hostname":"""#!/bin/sh
echo srv-deb-05
""",
      "flock":"""#!/bin/sh
exit 0
""",
      "gh":"""#!/bin/sh
exit 0
""",
      "python3":"""#!/bin/sh
if [ "$1" = "-m" ]; then exit 0; fi
mkdir -p "$HOME/.local/state/aiops2-proactive"
cat > "$HOME/.local/state/aiops2-proactive/candidate.json" <<'JSON'
{"state":"CI_PENDING","deploy_authorized":false}
JSON
""",
      "crontab":"""#!/bin/bash
if [[ "$1" == "-l" ]]; then cat "$FAKE_CRONTAB"; exit 0; fi
count=0
[[ -f "$FAKE_COUNT" ]] && count=$(cat "$FAKE_COUNT")
count=$((count+1))
echo "$count" > "$FAKE_COUNT"
cp "$1" "$FAKE_CRONTAB"
if [[ "$count" == 1 ]]; then exit 42; fi
"""
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
