# NOC UX — audit de captures locales existantes (2026-11-16)

Scope: evidence review only; **not** an exact-Git-SHA browser qualification and **not** a LIVE attestation. Owner 2/5; target integration/aiops2-convergence-20261114; dependency #713 and prototype #771 / browser gates #778, #780.

## Inputs inspected
Previously generated local sandbox artifacts under `/mnt/data/noc_qualification/`: `browser-results.json`, `noc-320.png`, `noc-768.png`, `noc-1440.png`. These artifacts are **not committed to GitHub**; availability is local to the conversation sandbox. The manifest declares source SHA-256 `9e1855d5ee38c7c09c48185236411b33ca69315da433a0506debfd98d084f24e` but does not identify an independently verified Git source SHA.

| Declared viewport | PNG bytes | Recomputed SHA-256 | Pillow verify() |
| --- | ---: | --- | --- |
| 320 | 225823 | `da9d74c58a780955d0c5266a4a3bef235d2954abc1050de15da18fa607ac832d` | PASS |
| 768 | 234175 | `28f09a0684b25a62b2fdeeca54f1cb385f2bd6e644bb91588fa49964954fcd78` | PASS |
| 1440 | 231701 | `8feca195961ad02e845ca591596eb7af9f302a716baa013781d0f83406dced9e` | PASS |

Executed in a local container:
```bash
python - <<'PY'
from PIL import Image
from pathlib import Path
import hashlib
for p in Path('/mnt/data/noc_qualification').glob('*.png'):
    im=Image.open(p)
    im.verify()
    print(p.name,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
PY
```
Result: 3/3 PNG structural decodes and hash recomputations completed without error; all hashes match the pre-existing manifest. This is **artifact integrity only**. It does not rerun Playwright, prove origin of screenshots, inspect accessibility, establish a source Git SHA, or attest the SAN→Payments path.

## Qualification and decision
- Existing manifest **claims** offline Chromium/Playwright `set_content`, zero external requests, and no horizontal overflow at 320/768/1440. These assertions were **not independently rerun in this increment**.
- Browser on exact #771/#778/#780 source: **NOT_TESTED**. CI: **UNKNOWN**. Screen-reader audit: **NOT_TESTED**. SAN→Payments evidence provenance/freshness/graph version: **UNKNOWN**.
- No authorization inferred from Analyst/Critic. Policy `DENY_LIVE`, HITL required; DEMO/SIMULATION only; **HOLD / NO-GO LIVE**.
- Next: architect to select one owning branch for prototype and gates; run browser against exact committed HTML with no network, capture persistent artifacts and source Git SHA, then verify focus, contrast, labels and overflow before replacing any static Portal view.
- Rollback: exclude this documentation-only branch/PR. No runtime, host, production, scheduler or shared source changes.
