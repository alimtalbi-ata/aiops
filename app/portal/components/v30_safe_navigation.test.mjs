import test from "node:test";
import assert from "node:assert/strict";
import { V30_SECTIONS, resolveV30Presentation, renderV30Navigation } from "./v30_safe_navigation.mjs";

test("six distinct canonical sections and semantic navigation", () => {
  assert.equal(V30_SECTIONS.length, 6);
  assert.equal(new Set(V30_SECTIONS.map(([slug]) => slug)).size, 6);
  const html = renderV30Navigation({ mode: "DEMO", active: "incident-itsm" });
  assert.match(html, /aria-label="Espaces V30"/);
  assert.match(html, /aria-current="page"/);
  assert.equal((html.match(/<li>/g) || []).length, 6);
  assert.match(html, /data-mode="DEMO"/);
  assert.match(html, /data-live="false"/);
});

test("LIVE is fail closed even with caller-supplied flags", () => {
  for (const props of [{}, {mode:"LIVE"}, {mode:"LIVE",liveAttested:true}, {mode:"LIVE",tenantAuthorized:true}, {mode:"live",liveAttested:true,tenantAuthorized:true}, {mode:"LIVE",liveAttested:1,tenantAuthorized:true}]) {
    assert.deepEqual(resolveV30Presentation(props), {mode:"UNKNOWN",trust:"UNVERIFIED",live:false});
  }
  assert.deepEqual(resolveV30Presentation({mode:"LIVE",liveAttested:true,tenantAuthorized:true}), {mode:"UNKNOWN",trust:"UNVERIFIED",live:false});
  assert.match(renderV30Navigation({mode:"LIVE",liveAttested:true,tenantAuthorized:true}), /data-live="false"/);
});

test("DEMO and REPLAY remain visibly non-LIVE even with attestations", () => {
  for (const mode of ["DEMO", "REPLAY"]) {
    const html = renderV30Navigation({mode,liveAttested:true,tenantAuthorized:true});
    assert.match(html, new RegExp(`data-mode="${mode}"`));
    assert.match(html, /data-live="false"/);
  }
});

test("untrusted active value cannot inject markup or alter anchors", () => {
  const html = renderV30Navigation({mode:"LIVE",active:'"><script>alert(1)</script>'});
  assert.doesNotMatch(html, /<script>/);
  assert.doesNotMatch(html, /aria-current="page"/);
  assert.equal((html.match(/href="#v30-/g) || []).length, 6);
});
