const { test } = require("node:test");
const assert = require("node:assert/strict");
const { evaluate, Monitor } = require("../chrome-extension/core.js");
const { fakeAdapter, message, fixture, drain } = require("./helpers.cjs");

test("matches Vietnamese phones, international formats, case and captions", () => {
  for (const text of ["0901234567 CARE", "+84901234567 care", "0084 901 234 567 care", "84 901 234 567 care",
    "(090) 123-4567 care", "0901.234.567\ncare", "care: 0363704915"]) assert.equal(evaluate(text).matched, true, text);
});

test("rejects invalid phones, longer digit strings and keyword substrings", () => {
  for (const text of ["care", "0901234567 zalo", "0901234567 healthcare", "0901234567 care_foo", "090123456 care",
    "09012345678 care", "0901234567 8 care", "0123456789 care", "abc0901234567 care", "09012\n34567 care", ""]) {
    assert.equal(evaluate(text).matched, false, text);
  }
});

test("keywords are literal, Unicode-aware and support phrases", () => {
  assert.equal(evaluate("0901234567 care+", "care+").matched, true);
  assert.equal(evaluate("0901234567 careeee", "care+").matched, false);
  assert.equal(evaluate("0901234567 GỬI   ẢNH", "gửi ảnh").matched, true);
  assert.equal(evaluate("0901234567 careá", "care").matched, false);
  assert.equal(evaluate("0901234567 care", " ").matched, false);
});

test("only new incoming matching messages in the selected group are sent", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  for (const value of [message({ pFlags: { out: true } }), message({ fromId: 1 }), message({ date: 999 }),
    message({ peerId: -20 }), message({ message: "0901234567 zalo" }), message({ _: "messageService" })]) {
    assert.equal(f.monitor.enqueue(value), false);
  }
  f.adapter.emit(message());
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 1);
  assert.equal(f.monitor.counts.sent, 1);
});

test("duplicate events and successful receipts never send twice", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.emit(message());
  f.adapter.emit(message());
  await drain(f.monitor);
  f.adapter.emit(message());
  assert.equal(f.adapter.sent.length, 1);
  assert.equal(f.monitor.counts.matched, 1);
  assert.ok(f.adapter.receipts.has("1:-10:4294967419"));
});

test("dry run never sends or writes receipts and does not block a later live run", async (t) => {
  const f = fixture({ dryRun: true }); t.after(() => f.monitor.stop());
  f.adapter.emit(message()); await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 0);
  assert.equal(f.adapter.receipts.size, 0);
  assert.equal(f.monitor.counts.preview, 1);
  f.monitor.stop();
  f.monitor.start({ keyword: "care", interval: 1.5, dryRun: false });
  f.adapter.emit(message()); await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 1);
});

test("an existing manual reaction with chosen_order zero is preserved", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.emit(message({ reactions: { results: [{ chosen_order: 0 }] } }));
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 0);
  assert.equal(f.monitor.counts.skipped, 1);
});

test("other peoples reactions do not block clap", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.emit(message({ reactions: { results: [{ count: 5 }] } }));
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 1);
});

test("an edit or deletion before sending is checked again", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.emit(message());
  f.adapter.messages.set(message().mid, message({ message: "0901234567 zalo" }));
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 0);
  assert.equal(f.adapter.receipts.size, 0);
});

test("pacing is enforced between messages", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.emit(message());
  f.adapter.emit(message({ id: 124, mid: 4294967420 }));
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 2);
  assert.ok(f.sleeps.includes(1500));
});

test("FloodWait stores a shared cooldown and retries after the required wait", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  let attempts = 0;
  f.adapter.send = async () => { if (++attempts === 1) throw { type: "FLOOD_WAIT_30" }; };
  f.adapter.emit(message()); await drain(f.monitor);
  assert.equal(attempts, 2);
  assert.ok(f.sleeps.includes(31000));
  assert.equal(f.adapter.cooldowns.get("1"), 1_031_000);
  assert.equal(f.monitor.counts.sent, 1);
});

test("Stop interrupts a long wait and cancels the pending queue", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.send = async () => { throw { type: "FLOOD_WAIT_3600" }; };
  const { pause } = require("../chrome-extension/core.js");
  f.monitor.sleep = pause;
  f.adapter.emit(message());
  f.adapter.emit(message({ id: 124, mid: 4294967420 }));
  for (let attempt = 0; !f.monitor.waitUntil && attempt < 10; attempt++) await new Promise(setImmediate);
  assert.ok(f.monitor.waitUntil);
  f.monitor.stop();
  await drain(f.monitor);
  assert.equal(f.monitor.running, false);
  assert.equal(f.monitor.queue.length, 0);
  assert.equal(f.adapter.listeners.size, 0);
  assert.equal(f.adapter.receipts.size, 0);
});

test("switching chat or account stops without sending into the new context", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.current.peer = "-20";
  assert.equal(f.monitor.enqueue(message()), false);
  assert.equal(f.monitor.running, false);
  assert.equal(f.adapter.sent.length, 0);
});

test("permission errors are logged without success receipts or message bodies", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.send = async () => { throw { type: "REACTION_INVALID" }; };
  f.adapter.emit(message()); await drain(f.monitor);
  assert.equal(f.monitor.counts.failed, 1);
  assert.equal(f.adapter.receipts.size, 0);
  assert.match(f.monitor.logs.at(-1).message, /chưa cho phép/);
  assert.doesNotMatch(JSON.stringify(f.monitor.snapshot()), /0901234567/);
});

test("two tabs watching the same group share a lock and send only once", async (t) => {
  const shared = {};
  const a = fixture({}, fakeAdapter(shared));
  const b = fixture({}, fakeAdapter(shared));
  t.after(() => { a.monitor.stop(); b.monitor.stop(); });
  a.adapter.emit(message()); b.adapter.emit(message());
  await Promise.all([drain(a.monitor), drain(b.monitor)]);
  assert.equal(a.adapter.sent.length + b.adapter.sent.length, 1);
});

test("a server acknowledgement after Stop records the original account/group", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  let resolveSend;
  f.adapter.send = () => new Promise((resolve) => { resolveSend = resolve; });
  f.adapter.emit(message());
  for (let i = 0; !resolveSend && i < 10; i++) await new Promise(setImmediate);
  assert.ok(resolveSend);
  f.monitor.stop();
  f.adapter.current.peer = "-20";
  f.monitor.start({ keyword: "care", interval: 1.5, dryRun: false });
  resolveSend();
  await drain(f.monitor);
  assert.ok(f.adapter.receipts.has("1:-10:4294967419"));
  assert.equal(f.adapter.receipts.has("1:-20:4294967419"), false);
  assert.equal(f.monitor.counts.sent, 0);
});

test("start validates authentication, group selection and configuration", () => {
  const adapter = fakeAdapter();
  const monitor = new Monitor(adapter);
  adapter.current.peer = "123";
  assert.throws(() => monitor.start({ keyword: "care", interval: 1.5 }), /nhóm hoặc kênh/);
  adapter.current.peer = "-10";
  assert.throws(() => monitor.start({ keyword: "", interval: 1.5 }), /Từ khóa/);
  assert.throws(() => monitor.start({ keyword: "care", interval: 0 }), /Khoảng cách/);
});
