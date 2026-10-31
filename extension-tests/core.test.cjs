const { test } = require("node:test");
const assert = require("node:assert/strict");
const { evaluate, Monitor } = require("../chrome-extension/core.js");
const { fakeAdapter, message, fixture, drain } = require("./helpers.cjs");

test("matches Vietnamese phones without requiring care or another keyword", () => {
  for (const text of ["0901234567", "0901234567 zalo thu 15prm", "+84901234567 gửi ảnh",
    "0084 901 234 567 care", "84 901 234 567 zalo", "(090) 123-4567 care",
    "0901.234.567\ncare", "care: 0901234567", "0901234567 healthcare"]) {
    assert.equal(evaluate(text).matched, true, text);
  }
});

test("rejects missing or invalid phones and longer digit strings", () => {
  for (const text of ["care gửi ảnh", "HD zalo 14prm", "090123456 care",
    "09012345678 care", "0901234567 8 care", "0123456789 care", "abc0901234567 care", "09012\n34567 care", ""]) {
    assert.equal(evaluate(text).matched, false, text);
  }
});

test("uppercase pairs at the beginning after a phone exclude the whole message", () => {
  for (const code of ["HD", "HM", "HB", "AB", "ĐT", "CARE", "HDcare", "THING"]) {
    for (const separator of [" ", "\n", " : ", " - ", ", ", "\u00a0"]) {
      const text = `0901234567${separator}${code} gửi ảnh`;
      assert.equal(evaluate(text).matched, false, text);
      assert.match(evaluate(text).reason, /Bỏ qua/);
    }
  }
});

test("standalone TH is explicitly allowed, including without care", () => {
  for (const text of ["0901234567 TH care 18pro", "0901234567 TH zalo 14prm",
    "+84 901 234 567: TH gửi ảnh", "0901234567\nTH", "0901234567 TH - 14prm"]) {
    assert.equal(evaluate(text).matched, true, text);
  }
  for (const token of ["THA", "THcare", "TH1", "TH_foo"]) {
    assert.equal(evaluate(`0901234567 ${token}`).matched, false, token);
  }
});

test("single uppercase, mixed case and uppercase later in the text stay eligible", () => {
  for (const text of ["0901234567 H gửi ảnh", "0901234567 Hd care", "0901234567 hD zalo",
    "0901234567 hd care", "0901234567 care HD", "HD: 0901234567 care", "0901234567 H D care"]) {
    assert.equal(evaluate(text).matched, true, text);
  }
});

test("one forbidden phone suffix excludes a multi-phone message, even alongside TH", () => {
  assert.equal(evaluate("0901234567 care; 0971234567 HM zalo").matched, false);
  assert.equal(evaluate("0901234567 TH care; 0971234567 HD zalo").matched, false);
  assert.equal(evaluate("0901234567 TH care; 0971234567 zalo").matched, true);
});

test("preview remains deterministic across repeated and Unicode-normalized input", () => {
  for (let attempt = 0; attempt < 4; attempt++) {
    assert.equal(evaluate("0901234567 TH gửi ảnh").matched, true);
    assert.equal(evaluate("0901234567 ĐT gửi ảnh".normalize("NFD")).matched, false);
  }
});

test("only new incoming matching messages in the selected group are sent", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  for (const value of [message({ pFlags: { out: true } }), message({ fromId: 1 }), message({ date: 999 }),
    message({ peerId: -20 }), message({ message: "0901234567 HD zalo" }), message({ _: "messageService" })]) {
    assert.equal(f.monitor.enqueue(value), false);
  }
  f.adapter.emit(message());
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 1);
  assert.equal(f.monitor.counts.sent, 1);
});

test("queue sends TH and ordinary phone comments but excludes HD HM HB", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  const bodies = ["0901234567 care", "0901234567 TH zalo", "0901234567 zalo",
    "0901234567 HD care", "0901234567 HM zalo", "0901234567 HB zalo"];
  bodies.forEach((text, index) => f.adapter.emit(message({ id: 123 + index, mid: 4294967419 + index, message: text })));
  await drain(f.monitor);
  assert.deepEqual(f.adapter.sent.map((item) => item.id), [123, 124, 125]);
  assert.equal(f.monitor.counts.matched, 3);
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
  f.monitor.start({ interval: 1.5, dryRun: false });
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
  f.adapter.messages.set(message().mid, message({ message: "0901234567 HD zalo" }));
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 0);
  assert.equal(f.adapter.receipts.size, 0);
});

test("a deleted message is skipped when reread before sending", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.emit(message());
  f.adapter.messages.delete(message().mid);
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 0);
  assert.equal(f.monitor.counts.skipped, 1);
});

test("an allowed TH prefix edited to HM before sending no longer receives a reaction", async (t) => {
  const f = fixture(); t.after(() => f.monitor.stop());
  f.adapter.emit(message({ message: "0901234567 TH care" }));
  f.adapter.messages.set(message().mid, message({ message: "0901234567 HM care" }));
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 0);
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
  f.monitor.start({ interval: 1.5, dryRun: false });
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
  assert.throws(() => monitor.start({ interval: 1.5 }), /nhóm hoặc kênh/);
  adapter.current.peer = "-10";
  assert.throws(() => monitor.start({ interval: 0 }), /Khoảng cách/);
});

test("old keyword settings are ignored and cannot restrict the new rules", async (t) => {
  const f = fixture({ keyword: "gửi ảnh" }); t.after(() => f.monitor.stop());
  f.adapter.emit(message({ message: "0901234567 zalo" }));
  await drain(f.monitor);
  assert.equal(f.adapter.sent.length, 1);
  assert.equal("keyword" in f.monitor.snapshot().config, false);
});
