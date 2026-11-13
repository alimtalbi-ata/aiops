import test from 'node:test';
import assert from 'node:assert/strict';
import { SAN_PAYMENTS_STEPS, describeSanPaymentsJourney, renderSanPaymentsJourney } from './san_payments_journey.mjs';

test('synthetic: eight stages are ordered, missing data is UNKNOWN and never approved', () => {
  const steps = describeSanPaymentsJourney();
  assert.equal(steps.length, 8);
  assert.deepEqual(steps.map(s => s.id), SAN_PAYMENTS_STEPS.map(s => s.id));
  assert.ok(steps.every(s => s.state === 'UNKNOWN' && s.isOperationalClaim === false));
});

test('synthetic: forged READY and missing decision cannot imply human approval', () => {
  const steps = describeSanPaymentsJourney({
    decision: { state: 'READY', detail: 'synthetic: approved' },
    result: { state: 'BLOCKED', detail: 'synthetic: blocked' }
  });
  assert.equal(steps[6].state, 'UNKNOWN');
  assert.equal(steps[7].state, 'BLOCKED');
  assert.equal(steps[6].isOperationalClaim, false);
});

test('synthetic: semantic ordered navigation, text-only untrusted content and provenance', () => {
  const nodes = [];
  const document = { createElement(tag) {
    const node = { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
    nodes.push(node); return node;
  }};
  const root = { children: [], append(node) { this.children.push(node); } };
  const nav = renderSanPaymentsJourney(document, root, {
    incident: { state: 'ERROR', detail: '<script>alert(1)</script>', source: 'SYNTHETIC' }
  });
  assert.equal(nav.tag, 'nav');
  assert.match(nav.attributes['aria-label'], /SAN vers Payments/);
  const list = nav.children[2];
  assert.equal(list.tag, 'ol');
  assert.equal(list.children.length, 8);
  assert.equal(list.children[0].children[2].textContent, '<script>alert(1)</script>');
  assert.match(list.children[0].children[4].textContent, /SYNTHETIC/);
  assert.equal(root.children[0], nav);
  assert.equal(nodes.filter(n => n.tag === 'script').length, 0);
});

test('synthetic: all states expose actionable guidance without claiming freshness', () => {
  const states = ['LOADING', 'EMPTY', 'ERROR', 'UNKNOWN', 'BLOCKED', 'AVAILABLE'];
  for (const state of states) {
    const step = describeSanPaymentsJourney({ incident: { state, observedAt: 'SYNTHETIC-2026-01-01' } })[0];
    assert.equal(step.state, state);
    assert.ok(step.guidance.length > 15);
    assert.equal(step.isOperationalClaim, false);
  }
});

test('synthetic: provenance and guidance are text, not inferred evidence', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k,v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { append() {} };
  const nav = renderSanPaymentsJourney(document, root, {
    decision: { state: 'BLOCKED', source: 'SYNTHETIC', observedAt: 'not verified' }
  });
  const decision = nav.children[2].children[6];
  assert.match(decision.children[3].textContent, /Policy\/HITL/);
  assert.match(decision.children[4].textContent, /Source déclarée : SYNTHETIC/);
  assert.match(decision.children[4].textContent, /Horodatage déclaré : not verified/);
});

test('synthetic: null, undefined and primitive payloads fail closed to UNKNOWN', () => {
  for (const payload of [null, undefined, false, 0, 'SYNTHETIC malformed response']) {
    const steps = describeSanPaymentsJourney(payload);
    assert.equal(steps.length, 8);
    assert.ok(steps.every(step => step.state === 'UNKNOWN' && !step.isOperationalClaim));
  }
});

test('synthetic: rendering with null response retains eight accessible UNKNOWN steps', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { children: [], append(node) { this.children.push(node); } };
  const nav = renderSanPaymentsJourney(document, root, null);
  assert.equal(nav.tag, 'nav');
  assert.ok(nav.attributes['aria-label']);
  const list = nav.children[2];
  assert.equal(list.tag, 'ol');
  assert.equal(list.children.length, 8);
  assert.ok(list.children.every(item => item.attributes['data-state'] === 'UNKNOWN'));
});

test('synthetic: throwing record getter fails closed without hiding other stages', () => {
  const records = {
    get incident() { throw new Error('SYNTHETIC adapter failure'); },
    impact: { state: 'BLOCKED', source: 'SYNTHETIC' }
  };
  const steps = describeSanPaymentsJourney(records);
  assert.equal(steps.length, 8);
  assert.equal(steps[0].state, 'UNKNOWN');
  assert.equal(steps[1].state, 'BLOCKED');
  assert.equal(steps[1].source, 'SYNTHETIC');
});

test('synthetic: throwing metadata getter cannot publish partial AVAILABLE claim', () => {
  const records = {
    decision: {
      state: 'AVAILABLE',
      detail: 'SYNTHETIC unverified',
      get source() { throw new Error('SYNTHETIC metadata failure'); }
    },
    result: { state: 'BLOCKED' }
  };
  const steps = describeSanPaymentsJourney(records);
  assert.equal(steps[6].state, 'UNKNOWN');
  assert.equal(steps[6].detail, 'Aucune information vérifiée');
  assert.equal(steps[7].state, 'BLOCKED');
  assert.ok(steps.every(step => !step.isOperationalClaim));
});

test('synthetic: hostile Proxy and array records cannot crash rendering', () => {
  const records = new Proxy({}, {
    getOwnPropertyDescriptor() { throw new Error('SYNTHETIC proxy failure'); }
  });
  const steps = describeSanPaymentsJourney(records);
  assert.ok(steps.every(step => step.state === 'UNKNOWN'));
  assert.equal(describeSanPaymentsJourney({ run: [{ state: 'AVAILABLE' }] })[3].state, 'UNKNOWN');
});

test('synthetic: every stage has a separate explicit text status for screen readers', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { append() {} };
  const nav = renderSanPaymentsJourney(document, root, {
    incident: { state: 'LOADING' }, decision: { state: 'BLOCKED' }
  });
  const items = nav.children[2].children;
  assert.equal(items.length, 8);
  assert.equal(items[0].children[1].textContent, 'État : LOADING');
  assert.equal(items[6].children[1].textContent, 'État : BLOCKED');
  assert.equal(items[7].children[1].textContent, 'État : UNKNOWN');
  assert.ok(items.every(item => item.children[1].tag === 'span'));
});

test('synthetic: AVAILABLE is visibly consultable but never validated or READY', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { append() {} };
  const nav = renderSanPaymentsJourney(document, root, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC', observedAt: 'not verified' },
    decision: { state: 'BLOCKED' }
  });
  const items = nav.children[2].children;
  assert.equal(items[0].children[1].textContent,
    'État : AVAILABLE (données consultables, non validées)');
  assert.equal(items[6].children[1].textContent, 'État : BLOCKED');
  assert.equal(items[7].children[1].textContent, 'État : UNKNOWN');
  assert.match(items[0].children[4].textContent, /Source déclarée : SYNTHETIC/);
  assert.ok(describeSanPaymentsJourney({ incident: { state: 'AVAILABLE' } })
    .every(step => step.isOperationalClaim === false));
});

test('synthetic: demo coverage summary counts only displayed stages, never platform health', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const root = { append() {} };
  const nav = renderSanPaymentsJourney(document, root, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC' },
    impact: { state: 'BLOCKED' },
    noc: { state: 'ERROR' },
    run: { state: 'LOADING' }
  });
  assert.equal(nav.children[2].children.length, 8);
  const summary = nav.children[3];
  assert.equal(summary.tag, 'p');
  assert.match(summary.textContent, /5 étape\(s\) sans information exploitable/);
  assert.match(summary.textContent, /1 étape\(s\) bloquée\(s\)/);
  assert.match(summary.textContent, /1 étape\(s\) en chargement/);
  assert.match(summary.textContent, /pas un indicateur de santé/);
  assert.doesNotMatch(summary.textContent, /READY|production saine/);
});


test('synthetic: pending stages remain distinct from missing and blocked stages', () => {
  const document = { createElement(tag) {
    return { tag, children: [], textContent: '', attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'LOADING' }, impact: { state: 'LOADING' },
    noc: { state: 'BLOCKED' }
  });
  const summary = nav.children[3].textContent;
  assert.match(summary, /5 étape\(s\) sans information exploitable/);
  assert.match(summary, /1 étape\(s\) bloquée\(s\)/);
  assert.match(summary, /2 étape\(s\) en chargement/);
  assert.match(summary, /pas un indicateur de santé/);
});


test('synthetic: coverage breakdown distinguishes UNKNOWN, ERROR and EMPTY without implying health', () => {
  const document = { createElement(tag) {
    return { tag, children: [], textContent: '', attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'ERROR' }, impact: { state: 'EMPTY' },
    noc: { state: 'BLOCKED' }, run: { state: 'LOADING' },
    evidence: { state: 'AVAILABLE', source: 'SYNTHETIC' }
  });
  const summary = nav.children[3].textContent;
  assert.match(summary, /5 étape\(s\) sans information exploitable/);
  assert.match(summary, /UNKNOWN : 3, ERROR : 1, EMPTY : 1/);
  assert.match(summary, /1 étape\(s\) bloquée\(s\)/);
  assert.match(summary, /1 étape\(s\) en chargement/);
  assert.match(summary, /pas un indicateur de santé/);
});


test('synthetic: explicit synthetic provenance warning never implies production data', () => {
  const document = { createElement(tag) {
    return { tag, children: [], textContent: '', attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC', observedAt: 'not verified' },
    impact: { state: 'AVAILABLE', source: 'authorized source' }
  });
  const items = nav.children[2].children;
  assert.match(items[0].children[4].textContent, /DONNÉES SYNTHÉTIQUES — démonstration uniquement/);
  assert.match(items[0].children[4].textContent, /Source déclarée : SYNTHETIC/);
  assert.doesNotMatch(items[1].children[4].textContent, /DONNÉES SYNTHÉTIQUES/);
  assert.equal(items[0].children[1].textContent, 'État : AVAILABLE (données consultables, non validées)');
});


test('synthetic: missing provenance and freshness remain explicitly unverified even when AVAILABLE', () => {
  const document = { createElement(tag) {
    return { tag, children: [], textContent: '', attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE' },
    impact: { state: 'AVAILABLE', source: 'SYNTHETIC', observedAt: 'unverified demo timestamp' }
  });
  const items = nav.children[2].children;
  assert.match(items[0].children[4].textContent, /PROVENANCE INCOMPLÈTE/);
  assert.match(items[0].children[4].textContent, /FRAÎCHEUR INCONNUE/);
  assert.match(items[0].children[1].textContent, /non validées/);
  assert.doesNotMatch(items[1].children[4].textContent, /PROVENANCE INCOMPLÈTE|FRAÎCHEUR INCONNUE/);
  assert.match(items[1].children[4].textContent, /DONNÉES SYNTHÉTIQUES/);
});

test('synthetic: consultable stages are counted without implying validation', () => {
  const document = { createElement(tag) {
    return { tag, children: [], textContent: '', attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC' },
    impact: { state: 'AVAILABLE' },
    noc: { state: 'BLOCKED' },
    run: { state: 'LOADING' }
  });
  const summary = nav.children[3].textContent;
  assert.match(summary, /2 étape\(s\) consultable\(s\), non validée\(s\)/);
  assert.match(summary, /1 étape\(s\) bloquée\(s\)/);
  assert.match(summary, /1 étape\(s\) en chargement/);
  assert.match(summary, /pas un indicateur de santé/);
  assert.doesNotMatch(summary, /READY|approuvée|production saine/);
  assert.equal(nav.children[2].children.length, 8);
});


test('synthetic: provenance coverage counts missing metadata and declared demo sources separately', () => {
  const document = { createElement(tag) {
    return { tag, children: [], textContent: '', attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC', observedAt: 'unverified demo timestamp' },
    impact: { state: 'AVAILABLE', source: 'authorized adapter' },
    noc: { state: 'BLOCKED' }
  });
  const summary = nav.children[3].textContent;
  assert.match(summary, /6 source\(s\) non renseignée\(s\)/);
  assert.match(summary, /7 horodatage\(s\) inconnu\(s\)/);
  assert.match(summary, /1 source\(s\) SYNTHETIC/);
  assert.match(summary, /démonstration uniquement/);
  assert.match(summary, /pas un indicateur de santé/);
  assert.equal(nav.children[2].children.length, 8);
});

test('synthetic: declared synthetic source variants are never presented without demo warning', () => {
  const document = { createElement(tag) {
    return { tag, children: [], textContent: '', attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE', source: 'synthetic: acme fixture' },
    impact: { state: 'AVAILABLE', source: 'SYNTHETIC/replay' },
    noc: { state: 'BLOCKED', source: 'synthetic_fixture' },
    run: { state: 'UNKNOWN', source: 'synthetically named production adapter' }
  });
  const items = nav.children[2].children;
  for (const i of [0, 1, 2]) {
    assert.match(items[i].children[4].textContent, /DONNÉES SYNTHÉTIQUES/);
  }
  assert.doesNotMatch(items[3].children[4].textContent, /DONNÉES SYNTHÉTIQUES/);
  assert.match(nav.children[3].textContent, /3 source\(s\) SYNTHETIC/);
  assert.match(items[0].children[1].textContent, /non validées/);
});


test('synthetic: only pending stages expose aria-busy; BLOCKED and UNKNOWN are not busy', () => {
  const document = { createElement(tag) {
    return { tag, children: [], textContent: '', attributes: {},
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'LOADING' },
    impact: { state: 'BLOCKED' },
    noc: { state: 'ERROR' },
    run: { state: 'AVAILABLE', source: 'SYNTHETIC' }
  });
  const items = nav.children[2].children;
  assert.equal(items[0].attributes['aria-busy'], 'true');
  assert.ok(items.slice(1).every(item => !Object.hasOwn(item.attributes, 'aria-busy')));
  assert.equal(items[1].attributes['data-state'], 'BLOCKED');
  assert.equal(items[4].attributes['data-state'], 'UNKNOWN');
});

test('synthetic: mode declaration defaults UNKNOWN and never labels a LIVE session', () => {
  const document = { createElement(tag) {
    return { tag, children: [], attributes: {}, textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const render = options => renderSanPaymentsJourney(document, { append() {} },
    { incident: { state: 'AVAILABLE', source: 'SYNTHETIC' } }, options);
  const unknown = render();
  assert.match(unknown.children[1].textContent, /Mode : UNKNOWN.*LIVE non revendiqué/);
  assert.match(render({ mode: 'LIVE' }).children[1].textContent, /Mode : UNKNOWN/);
  assert.match(render({ mode: 'DEMO' }).children[1].textContent, /Mode : DEMO.*aucune opération LIVE/);
  assert.match(render({ mode: 'REPLAY' }).children[1].textContent, /Mode : REPLAY/);
  assert.match(render({ mode: 'READY' }).children[1].textContent, /Mode : UNKNOWN/);
  assert.match(render(new Proxy({}, { get() { throw Error('synthetic failure'); } }))
    .children[1].textContent, /Mode : UNKNOWN/);
  assert.equal(unknown.children[2].children[0].attributes['data-state'], 'AVAILABLE');
});


test('synthetic: accessible navigation and CSS mode always fail closed for LIVE or invalid mode', () => {
  const document = { createElement(tag) {
    return { tag, children: [], attributes: {}, textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const render = options => renderSanPaymentsJourney(document, { append() {} }, {}, options);
  for (const [options, expected] of [[undefined, 'UNKNOWN'], [{ mode: 'LIVE' }, 'UNKNOWN'],
    [{ mode: 'DEMO' }, 'DEMO'], [{ mode: 'REPLAY' }, 'REPLAY'], [{ mode: 'READY' }, 'UNKNOWN']]) {
    const nav = render(options);
    assert.equal(nav.attributes['data-mode'], expected);
    assert.match(nav.attributes['aria-label'], new RegExp('mode ' + expected + '$'));
    assert.equal(nav.children[2].children.length, 8);
  }
});

test('synthetic: a supplied timestamp is declarative, never proof of freshness', () => {
  const document = { createElement(tag) {
    return { tag, children: [], attributes: {}, textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC', observedAt: '2026-11-12T12:00:00Z' }
  }, { mode: 'DEMO' });
  assert.match(nav.children[2].children[0].children[4].textContent,
    /Horodatage déclaré : 2026-11-12T12:00:00Z/);
  assert.match(nav.children[3].textContent,
    /horodatages renseignés sont déclaratifs et ne prouvent pas la fraîcheur/);
  assert.match(nav.children[1].textContent, /Mode : DEMO/);
  assert.doesNotMatch(nav.children[3].textContent, /production saine|READY/);
});


test('synthetic: DEMO and REPLAY have distinct accessible provenance warnings', () => {
  const document = { createElement(tag) {
    return { tag, children: [], attributes: {}, textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const render = mode => renderSanPaymentsJourney(document, { append() {} }, {}, { mode });
  const demo = render('DEMO');
  const replay = render('REPLAY');
  const unknown = render('LIVE');
  assert.match(demo.children[1].textContent, /démonstration uniquement, aucune opération LIVE/);
  assert.match(replay.children[1].textContent, /rejeu déclaré, données historiques non attestées/);
  assert.match(replay.children[1].textContent, /aucune opération LIVE/);
  assert.match(unknown.children[1].textContent, /mode non attesté, LIVE non revendiqué/);
  assert.equal(replay.attributes['data-mode'], 'REPLAY');
  assert.equal(unknown.attributes['data-mode'], 'UNKNOWN');
  assert.equal(replay.children[2].children.length, 8);
});

test('synthetic: provenance styling hook distinguishes demo, missing and unverified metadata', () => {
  const document = { createElement(tag) {
    return { tag, children: [], attributes: {}, textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE', source: 'synthetic: fixture', observedAt: '2026-11-12' },
    impact: { state: 'AVAILABLE', source: 'adapter', observedAt: '2026-11-12' },
    noc: { state: 'AVAILABLE', source: 'adapter' },
    run: { state: 'BLOCKED' }
  }, { mode: 'DEMO' });
  const items = nav.children[2].children;
  assert.deepEqual(items.slice(0, 4).map(item => item.attributes['data-provenance']),
    ['SYNTHETIC', 'DECLARED_UNVERIFIED', 'INCOMPLETE', 'INCOMPLETE']);
  assert.equal(nav.attributes['data-mode'], 'DEMO');
  assert.equal(items[3].attributes['data-state'], 'BLOCKED');
  assert.equal(items.length, 8);
  assert.match(items[1].children[4].textContent, /Horodatage déclaré/);
});


test('synthetic: freshness remains UNKNOWN even when a source is explicitly SYNTHETIC', () => {
  const document = { createElement(tag) {
    return { tag, children: [], attributes: {}, textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const nav = renderSanPaymentsJourney(document, { append() {} }, {
    incident: { state: 'AVAILABLE', source: 'SYNTHETIC' },
    impact: { state: 'AVAILABLE', source: 'authorized adapter', observedAt: '2026-11-12T12:00:00Z' },
    noc: { state: 'BLOCKED' }
  }, { mode: 'DEMO' });
  const items = nav.children[2].children;
  assert.equal(items[0].attributes['data-provenance'], 'SYNTHETIC');
  assert.equal(items[0].attributes['data-freshness'], 'UNKNOWN');
  assert.equal(items[1].attributes['data-freshness'], 'DECLARED_UNVERIFIED');
  assert.equal(items[2].attributes['data-freshness'], 'UNKNOWN');
  assert.equal(items[2].attributes['data-state'], 'BLOCKED');
  assert.match(items[0].children[4].textContent, /FRAÎCHEUR INCONNUE/);
  assert.match(nav.children[3].textContent, /horodatage\(s\) inconnu\(s\)/);
});

test('synthetic: inherited adapter state and metadata never become trusted declarations', () => {
  const inheritedState = Object.create({ state: 'AVAILABLE', source: 'forged', observedAt: 'forged' });
  const inheritedMetadata = Object.assign(
    Object.create({ source: 'forged LIVE source', observedAt: 'forged freshness', detail: 'forged detail' }),
    { state: 'AVAILABLE' }
  );
  const steps = describeSanPaymentsJourney({
    incident: inheritedState,
    impact: inheritedMetadata,
    noc: { state: 'BLOCKED', source: 'SYNTHETIC' }
  });
  assert.equal(steps[0].state, 'UNKNOWN');
  assert.equal(steps[1].state, 'AVAILABLE');
  assert.equal(steps[1].source, 'Source non renseignée');
  assert.equal(steps[1].observedAt, 'Fraîcheur inconnue');
  assert.equal(steps[1].detail, 'Aucune information vérifiée');
  assert.equal(steps[2].state, 'BLOCKED');
  assert.ok(steps.every(step => step.isOperationalClaim === false));
});


test('synthetic: throwing adapter getter discards partial AVAILABLE and keeps other steps', () => {
  const partial = { state: 'AVAILABLE', source: 'claimed live adapter' };
  Object.defineProperty(partial, 'detail', { get() { throw Error('synthetic adapter failure'); } });
  const steps = describeSanPaymentsJourney({
    incident: partial,
    impact: { state: 'BLOCKED', source: 'SYNTHETIC' }
  });
  assert.equal(steps[0].state, 'UNKNOWN');
  assert.equal(steps[0].detail, 'Aucune information vérifiée');
  assert.equal(steps[0].source, 'Source non renseignée');
  assert.equal(steps[0].observedAt, 'Fraîcheur inconnue');
  assert.equal(steps[1].state, 'BLOCKED');
  assert.ok(steps.every(step => step.isOperationalClaim === false));
});

test('synthetic: changing mode getter is read once and cannot inject LIVE', () => {
  const document = { createElement(tag) {
    return { tag, children: [], attributes: {}, textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  let reads = 0;
  const options = { get mode() { reads++; return reads === 1 ? 'DEMO' : 'LIVE'; } };
  const nav = renderSanPaymentsJourney(document, { append() {} }, {}, options);
  assert.equal(reads, 1);
  assert.equal(nav.attributes['data-mode'], 'DEMO');
  assert.match(nav.children[1].textContent, /aucune opération LIVE/);
  assert.equal(nav.children[2].children.length, 8);
});


test('synthetic: inherited mode metadata cannot declare DEMO or REPLAY', () => {
  const document = { createElement(tag) {
    return { tag, children: [], attributes: {}, textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  for (const inherited of ['DEMO', 'REPLAY']) {
    const options = Object.create({ mode: inherited });
    const nav = renderSanPaymentsJourney(document, { append() {} }, {}, options);
    assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
    assert.match(nav.children[1].textContent, /LIVE non revendiqué/);
    assert.equal(nav.children[2].children.length, 8);
  }
  const explicit = Object.assign(Object.create({ mode: 'REPLAY' }), { mode: 'DEMO' });
  assert.equal(renderSanPaymentsJourney(document, { append() {} }, {}, explicit)
    .attributes['data-mode'], 'DEMO');
});

test('synthetic: throwing mode getter and hostile options Proxy fail closed without hiding stages', () => {
  const document = { createElement(tag) {
    return { tag, attributes: {}, children: [], textContent: '',
      setAttribute(k, v) { this.attributes[k] = v; },
      append(...items) { this.children.push(...items); } };
  }};
  const hostileOptions = [
    { get mode() { throw Error('synthetic mode getter failure'); } },
    new Proxy({}, { getOwnPropertyDescriptor() { throw Error('synthetic proxy failure'); } }),
    { mode: 'LIVE' }
  ];
  for (const options of hostileOptions) {
    const nav = renderSanPaymentsJourney(document, { append() {} }, {
      incident: { state: 'BLOCKED', source: 'SYNTHETIC' }
    }, options);
    assert.equal(nav.attributes['data-mode'], 'UNKNOWN');
    assert.match(nav.attributes['aria-label'], /mode UNKNOWN/);
    assert.match(nav.children[1].textContent, /LIVE non revendiqué/);
    assert.equal(nav.children[2].children.length, 8);
    assert.equal(nav.children[2].children[0].attributes['data-state'], 'BLOCKED');
  }
});


test('synthetic: forged completion and approval states fail closed across every journey stage', () => {
  for (const forbidden of ['READY', 'APPROVED', 'SUCCESS', 'HEALTHY', 'LIVE', 'RESOLVED']) {
    const records = Object.fromEntries(SAN_PAYMENTS_STEPS.map(step => [step.id, {
      state: forbidden, source: 'SYNTHETIC', observedAt: 'unverified timestamp',
      detail: 'synthetic: misleading completion'
    }]));
    const steps = describeSanPaymentsJourney(records);
    assert.equal(steps.length, 8);
    assert.ok(steps.every(step => step.state === 'UNKNOWN' && !step.isOperationalClaim));
    assert.ok(steps.every(step => step.source === 'Source non renseignée'));
    assert.ok(steps.every(step => step.observedAt === 'Fraîcheur inconnue'));
    assert.ok(steps.every(step => step.detail === 'Aucune information vérifiée'));
  }
});
