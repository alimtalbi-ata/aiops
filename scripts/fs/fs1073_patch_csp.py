#!/usr/bin/env python3
"""FS1073 candidate: allow exact dashboard inline assets by CSP hashes, never unsafe-inline."""
import ast,hashlib,base64,pathlib,re
html=pathlib.Path("/app/portal/fs1051_visual.html")
api=pathlib.Path("/app/portal/fs1051_visual.py")
s=html.read_text()
style=re.search(r"<style>(.*?)</style>",s,re.S)
js=re.search(r"<script>(.*?)</script>",s,re.S)
assert style and js
def hashval(value):
 return "'sha256-"+base64.b64encode(hashlib.sha256(value.encode("utf-8")).digest()).decode()+"'"
css_hash=hashval(style.group(1))
js_hash=hashval(js.group(1))
# Response-level policy explicitly permits only exact inline asset hashes and same-origin API fetch.
policy=("default-src 'none'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
        "form-action 'none'; script-src "+js_hash+"; style-src "+css_hash+"; "
        "connect-src 'self'; img-src 'self'; font-src 'self'")
source=api.read_text()
old='return HTMLResponse(Path(__file__).with_name("fs1051_visual.html").read_text(encoding="utf-8"))'
assert source.count(old)==1
new='return HTMLResponse(Path(__file__).with_name("fs1051_visual.html").read_text(encoding="utf-8"), headers={"Content-Security-Policy": '+repr(policy)+'})'
source=source.replace(old,new)
ast.parse(source)
api.write_text(source)
print("FS1073_CSP_PATCH=PASS")
print("FS1073_CSP_POLICY="+policy)
