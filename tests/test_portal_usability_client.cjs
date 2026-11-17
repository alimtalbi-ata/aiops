const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(require.resolve('../app/portal/portal_usability.js'), 'utf8');

class Node {
  constructor(tag, text = '') {
    this.tagName = tag.toUpperCase();
    this.children = [];
    this.parentNode = null;
    this.attributes = {};
    this.listeners = {};
    this.textContent = text;
    this.value = '';
    this.hidden = false;
    this.className = '';
    this.id = '';
  }
  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  insertBefore(child, before) {
    child.parentNode = this;
    const index = before ? this.children.indexOf(before) : -1;
    if (index < 0) this.children.push(child);
    else this.children.splice(index, 0, child);
    return child;
  }
  setAttribute(key, value) { this.attributes[key] = String(value); }
  addEventListener(name, fn) { this.listeners[name] = fn; }
  get firstChild() { return this.children[0] || null; }
  get nextSibling() {
    if (!this.parentNode) return null;
    const siblings = this.parentNode.children;
    return siblings[siblings.indexOf(this) + 1] || null;
  }
  get innerText() { return this.textContent + this.children.map(c => c.innerText || c.textContent || '').join(' '); }
  querySelector(selector) {
    if (selector === 'h1') return this.find(n => n.tagName === 'H1');
    if (selector === 'table') return this.find(n => n.tagName === 'TABLE');
    return null;
  }
  querySelectorAll(selector) {
    if (selector === 'tbody tr') {
      const tbody = this.find(n => n.tagName === 'TBODY');
      return tbody ? tbody.children : [];
    }
    return [];
  }
  find(predicate) {
    for (const child of this.children) {
      if (predicate(child)) return child;
      const found = child.find(predicate);
      if (found) return found;
    }
    return null;
  }
}

function fixture() {
  const body = new Node('body');
  const header = new Node('header');
  const headerNav = new Node('nav');
  header.appendChild(headerNav);
  body.appendChild(header);
  const main = new Node('main');
  body.appendChild(main);
  const h1 = new Node('h1', 'Operations Command Center');
  main.appendChild(h1);
  const runs = new Node('section');
  runs.id = 'runs';
  const table = new Node('table');
  const tbody = new Node('tbody');
  const rowA = new Node('tr', 'RUN-001 LIVE BLOCKED');
  const rowB = new Node('tr', 'RUN-002 DEMO RESOLVED');
  tbody.appendChild(rowA);
  tbody.appendChild(rowB);
  table.appendChild(tbody);
  runs.appendChild(table);
  main.appendChild(runs);
  const nodes = {'runs': runs};
  const document = {
    body, readyState: 'complete',
    createElement: tag => new Node(tag),
    querySelector(selector) {
      if (selector === 'main') return main;
      if (selector === 'header nav') return headerNav;
      return null;
    },
    getElementById(id) {
      if (id === 'portal-main') return main;
      if (nodes[id]) return nodes[id];
      return body.find(n => n.id === id);
    }
  };
  const window = {document};
  const context = vm.createContext({window, document, module: {exports: {}}, URL});
  vm.runInContext(source, context, {filename: 'portal_usability.js'});
  return {document, main, body, headerNav, runs, rowA, rowB, api: context.module.exports};
}

test('adds accessible skip link, operator quick navigation and quick actions', () => {
  const f = fixture();
  assert.equal(f.main.id, 'portal-main');
  assert.equal(f.document.getElementById('portal-skip-link').href, '#portal-main');
  assert.equal(f.document.getElementById('portal-workspace-nav').children.length, 7);
  assert.ok(f.document.getElementById('portal-quickstart'));
  assert.equal(f.headerNav.attributes['aria-label'], 'Navigation principale');
});

test('adds local Run filtering without network calls or hiding the source status', () => {
  const f = fixture();
  const input = f.document.getElementById('portal-run-filter-input');
  const result = f.document.getElementById('portal-run-filter');
  assert.ok(input);
  input.value = 'blocked';
  input.listeners.input();
  assert.equal(f.rowA.hidden, false);
  assert.equal(f.rowB.hidden, true);
  assert.match(result.textContent, /1 ligne/);
  input.value = '';
  input.listeners.input();
  assert.equal(f.rowA.hidden, false);
  assert.equal(f.rowB.hidden, false);
});

test('mount is idempotent and works as a progressive enhancement', () => {
  const f = fixture();
  assert.equal(f.api.mount(f.document), true);
  assert.equal(f.main.children.filter(n => n.id === 'portal-quickstart').length, 1);
  assert.equal(f.main.children.filter(n => n.id === 'portal-workspace-nav').length, 1);
  assert.equal(f.api.mount({querySelector: () => null}), false);
});
