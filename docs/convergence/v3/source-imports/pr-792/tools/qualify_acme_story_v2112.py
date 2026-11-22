"""Read-only static validation of ACME story browser behavior."""
import re
from pathlib import Path

def inspect_story(source):
    segment=source.split('def policy_story():',1)[1]
    events=re.findall(r'^  \["([^"]+)","([^"]+)"\],?$',segment,re.MULTILINE)
    checks={
      "ten_narrative_steps":len(events)==10,
      "next_button":'id="story-next"' in segment,
      "reset_button":'id="story-reset"' in segment,
      "next_handler":'addEventListener("click"' in segment and 'pos++' in segment,
      "reset_handler":'pos=-1;paint()' in segment,
      "terminal_disable":'pos===events.length-1' in segment,
      "no_network_writes":'fetch(' not in segment and 'post_json(' not in segment,
      "explicit_simulation":'FICTIF / SANS EFFET' in segment,
      "freeze_before_stop":next((i for i,(a,_) in enumerate(events) if a=="Policy — simulation"),99)<next((i for i,(a,_) in enumerate(events) if "STOP_AUTO" in a),-1),
    }
    return {"checks":checks,"steps":len(events),"passed":all(checks.values())}

def main():
    import json
    source=(Path(__file__).resolve().parents[1]/"app/portal/main.py").read_text()
    result=inspect_story(source)
    print(json.dumps(result,indent=2))
    raise SystemExit(0 if result["passed"] else 2)
if __name__=="__main__":main()
