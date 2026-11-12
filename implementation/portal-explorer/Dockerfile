# Builds on the exact already-qualified portal image, retaining GLPI ownership fixes.
ARG BASE_IMAGE=aiops2-portal:fs563-glpi-ownership-candidate-20261106
FROM ${BASE_IMAGE}
WORKDIR /app
COPY app/portal/explorer_api.py /app/portal/explorer_api.py
COPY app/portal/explorer_ui.html /app/portal/explorer_ui.html
COPY app/portal/explorer_ui.js /app/portal/explorer_ui.js
COPY tests/test_security.py /app/explorer_tests/test_security.py
RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/portal/main.py')
text=p.read_text()
marker='# FS621 read-only explorer mount'
if marker in text:
    raise SystemExit('explorer mount already exists in base image')
text += '\n' + marker + '\nfrom portal.explorer_api import mount as mount_explorer\nmount_explorer(app)\n'
p.write_text(text)
compile(text,str(p),'exec')
compile(Path('/app/portal/explorer_api.py').read_text(),'/app/portal/explorer_api.py','exec')
PY
RUN python3 -m pip install --no-cache-dir 'PyMySQL==1.1.1'
RUN python3 -m unittest discover -s /app/explorer_tests -v
