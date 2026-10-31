const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const { Monitor } = require("../chrome-extension/core.js");
const { fakeAdapter, message, drain } = require("./helpers.cjs");

const directory = path.join(__dirname, "../chrome-extension");
const tick = () => new Promise(setImmediate);

async function popup(t, options = {}) {
  const dom = new JSDOM(fs.readFileSync(path.join(directory, "popup.html"), "utf8"), {
    url: "https://extension.test/popup.html", runScripts: "outside-only",
  });
  const { window } = dom;
  const adapter = fakeAdapter();
  const monitor = new Monitor(adapter, () => {}, { now: () => 1_000_000 });
  const saved = [];
  let requests = 0;
  window.chrome = {
    storage: { local: {
      get: async () => ({ autoClapSettings: options.saved }),
      set: async (settings) => saved.push(settings),
    } },
    tabs: {
      query: async () => [{ id: 12, url: options.url || "https://web.telegram.org/k/#-10" }],
      create: async () => {},
      sendMessage: async (_tab, request) => {
        requests++;
        try {
          if (request.action === "start") monitor.start(request.config);
          if (request.action === "stop") monitor.stop();
          return { ok: true, context: adapter.context(), ...monitor.snapshot() };
        } catch (error) { return { ok: false, error: error.message }; }
      },
    },
  };
  t.after(() => { monitor.stop(); window.close(); });
  window.eval(fs.readFileSync(path.join(directory, "core.js"), "utf8"));
  window.eval(fs.readFileSync(path.join(directory, "popup.js"), "utf8"));
  await tick(); await tick();
  return { window, document: window.document, adapter, monitor, saved, requestCount: () => requests };
}

test("popup connects to the active group without asking for API credentials", async (t) => {
  const p = await popup(t);
  assert.equal(p.document.querySelector("#chat-name").textContent, "Nhóm kiểm thử");
  assert.equal(p.document.querySelector("#start").disabled, false);
  assert.equal(p.document.querySelector("#stop").disabled, true);
  assert.equal(p.document.querySelector("#api-id"), null);
  assert.equal(p.document.querySelector("#api-hash"), null);
});

test("popup Start and Stop control the monitor, and closing popup is independent", async (t) => {
  const p = await popup(t);
  p.document.querySelector("#dry-run").checked = true;
  p.document.querySelector("#start").click();
  await tick(); await tick();
  assert.equal(p.monitor.running, true);
  assert.equal(p.document.querySelector("#keyword").disabled, true);
  assert.equal(p.document.querySelector("#stop").disabled, false);
  p.adapter.emit(message()); await drain(p.monitor);
  assert.equal(p.monitor.counts.preview, 1);
  assert.equal(p.adapter.sent.length, 0);
  p.document.querySelector("#stop").click();
  await tick(); await tick();
  assert.equal(p.monitor.running, false);
  assert.equal(p.document.querySelector("#keyword").disabled, false);
  assert.equal(p.saved[0].autoClapSettings.dryRun, true);
});

test("wrong-tab popup explains how to open WebK and cannot start", async (t) => {
  const p = await popup(t, { url: "https://web.telegram.org/a/" });
  assert.equal(p.requestCount(), 0);
  assert.equal(p.document.querySelector("#start").disabled, true);
  assert.match(p.document.querySelector("#connection-note").textContent, /WebK/);
});

test("sample preview is local and uses the same phone/keyword rules", async (t) => {
  const p = await popup(t);
  assert.match(p.document.querySelector("#preview-result").textContent, /✓/);
  const before = p.requestCount();
  p.document.querySelector("#preview").value = "0901234567 healthcare";
  p.document.querySelector("#preview").dispatchEvent(new p.window.Event("input"));
  assert.match(p.document.querySelector("#preview-result").textContent, /○/);
  assert.equal(p.requestCount(), before);
});

test("empty keyword reports a useful error without starting", async (t) => {
  const p = await popup(t);
  p.document.querySelector("#keyword").value = "";
  p.document.querySelector("#start").click();
  await tick(); await tick();
  assert.equal(p.monitor.running, false);
  assert.match(p.document.querySelector("#notice").textContent, /Từ khóa/);
  assert.equal(p.document.querySelector("#start").disabled, false);
});

test("saved keyword and mode are restored", async (t) => {
  const p = await popup(t, { saved: { keyword: "gửi ảnh", interval: 3, dryRun: true } });
  assert.equal(p.document.querySelector("#keyword").value, "gửi ảnh");
  assert.equal(p.document.querySelector("#interval").value, "3");
  assert.equal(p.document.querySelector("#dry-run").checked, true);
});
