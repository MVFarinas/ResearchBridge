/*
 * Runs a packet's two inline scripts against a minimal DOM stub, answers the
 * first option of every question, presses Export, and prints a JSON summary.
 * Used by tests/test_packets.py; it checks the form code runs without errors.
 */
"use strict";
const fs = require("fs");

const html = fs.readFileSync(process.argv[2], "utf8");
const data = html.match(/<script type="application\/json" id="packet-data">([\s\S]*?)<\/script>/)[1];
const scripts = [...html.matchAll(/<script(?: id="rbbench-logic")?>([\s\S]*?)<\/script>/g)].map((m) => m[1]);

const byId = {};
const created = [];

/** A tiny element: attributes, children, text, listeners and a class set. */
class Element {
  constructor(tag) {
    this.tagName = tag;
    this.attributes = {};
    this.children = [];
    this.textContent = "";
    this.listeners = {};
    this.classes = new Set();
    this.classList = { toggle: (name, on) => (on ? this.classes.add(name) : this.classes.delete(name)) };
    this.value = "";
    this.checked = false;
    created.push(this);
  }
  setAttribute(name, value) {
    this.attributes[name] = String(value);
    if (name === "id") byId[value] = this;
  }
  appendChild(child) { this.children.push(child); return child; }
  addEventListener(type, handler) { this.listeners[type] = handler; }
  remove() {}
  click() {}
  scrollIntoView() {}
}

for (const id of ["packet-data", "title", "banner", "meta", "items", "progress", "status", "export", "next-missing"]) {
  new Element("div").setAttribute("id", id);
}
byId["packet-data"].textContent = data;
global.document = {
  createElement: (tag) => new Element(tag),
  createTextNode: (text) => ({ textContent: text }),
  getElementById: (id) => byId[id] || null,
  body: new Element("body"),
};
global.window = { localStorage: { getItem: () => null, setItem: () => {} } };
global.Blob = class { constructor(parts) { this.parts = parts; } };
global.URL = { createObjectURL: () => "blob:stub" };

// Run both scripts in one scope, as the browser would run them in order.
new Function("module", scripts.join("\n"))(undefined);

const radios = created.filter((e) => e.tagName === "input" && e.attributes.type === "radio");
const groups = new Map();
for (const radio of radios) if (!groups.has(radio.attributes.name)) groups.set(radio.attributes.name, radio);
const before = byId.progress.textContent;
for (const first of groups.values()) first.listeners.change();
byId.export.listeners.click();
process.stdout.write(JSON.stringify({
  radios: radios.length,
  groups: groups.size,
  before,
  after: byId.progress.textContent,
  status: byId.status.textContent,
  marks: created.filter((e) => e.tagName === "mark").length,
}));
