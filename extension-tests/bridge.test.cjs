const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const crypto = require("node:crypto");
const core = require("../chrome-extension/core.js");
const { fakeAdapter, message } = require("./helpers.cjs");

function bridge() {
  const origin = "https://web.telegram.org";
  const listeners = new Map();
  let runtimeListener;
  const adapter = fakeAdapter();
  const window = {
    addEventListener(name, callback) {
      if (!listeners.has(name)) listeners.set(name, []);
      listeners.get(name).push(callback);
    },
    postMessage(data) {
      queueMicrotask(() => {
        for (const callback of listeners.get("message") || []) callback({ data, source: window, origin });
      });
    },
  };
  const context = vm.createContext({
    window, location: { origin }, AutoClapCore: core,
    AutoClapWebK: { Adapter: class { constructor() { return adapter; } } },
    chrome: { runtime: { id: "test-extension", onMessage: { addListener(callback) { runtimeListener = callback; } } } },
    crypto, setTimeout, clearTimeout, setInterval, clearInterval,
  });
  for (const filename of ["main.js", "content.js"]) {
    vm.runInContext(fs.readFileSync(path.join(__dirname, "../chrome-extension", filename), "utf8"), context);
  }
  const control = (action, config = {}) => new Promise((resolve) => {
    runtimeListener({ type: "AUTOCLAP_CONTROL", action, config }, { id: "test-extension" }, resolve);
  });
  return { control, adapter, runtimeListener };
}

test("popup-to-content-to-page bridge controls the real queue end to end", async (t) => {
  const b = bridge();
  t.after(async () => { await b.control("stop"); });
  const initial = await b.control("status");
  assert.equal(initial.ok, true);
  assert.equal(initial.context.name, "Nhóm kiểm thử");
  assert.equal(initial.running, false);
  const started = await b.control("start", { keyword: "care", interval: 1.5, dryRun: true });
  assert.equal(started.running, true);
  b.adapter.emit(message({ date: Math.floor(Date.now() / 1000) }));
  await new Promise(setImmediate);
  const status = await b.control("status");
  assert.equal(status.counts.preview, 1);
  assert.equal(status.counts.sent, 0);
  assert.doesNotMatch(JSON.stringify(status), /0901234567/);
  const stopped = await b.control("stop");
  assert.equal(stopped.running, false);
  assert.equal(b.adapter.listeners.size, 0);
});

test("bridge accepts only its own extension and the known control actions", () => {
  const b = bridge();
  let responded = false;
  assert.equal(b.runtimeListener({ type: "AUTOCLAP_CONTROL", action: "start" }, { id: "other-extension" }, () => { responded = true; }), undefined);
  assert.equal(b.runtimeListener({ type: "AUTOCLAP_CONTROL", action: "exportSession" }, { id: "test-extension" }, () => { responded = true; }), undefined);
  assert.equal(responded, false);
});

test("extension manifest references complete local resources", () => {
  const directory = path.join(__dirname, "../chrome-extension");
  const manifest = JSON.parse(fs.readFileSync(path.join(directory, "manifest.json"), "utf8"));
  assert.equal(manifest.manifest_version, 3);
  assert.ok(fs.existsSync(path.join(directory, manifest.action.default_popup)));
  for (const entry of manifest.content_scripts) {
    for (const filename of entry.js) assert.ok(fs.existsSync(path.join(directory, filename)), filename);
  }
  assert.ok(manifest.content_scripts.some((entry) => entry.world === "MAIN"));
});
