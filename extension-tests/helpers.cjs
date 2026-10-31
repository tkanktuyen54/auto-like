const { Monitor } = require("../chrome-extension/core.js");

function fakeAdapter(shared = {}) {
  const receipts = shared.receipts ||= new Set();
  const attempts = shared.attempts ||= new Map();
  const cooldowns = shared.cooldowns ||= new Map();
  const listeners = new Set();
  const messages = new Map();
  const sent = [];
  const context = { ready: true, account: "1", peer: "-10", name: "Nhóm kiểm thử" };
  return {
    current: context, messages, sent, listeners, receipts, attempts, cooldowns,
    context: () => ({ ...context }),
    subscribe: (callback) => { listeners.add(callback); return () => listeners.delete(callback); },
    emit(message) { messages.set(message.mid, message); for (const listener of listeners) listener(message); },
    message: async (_peer, mid) => messages.get(mid),
    async withLock(_account, signal, callback) {
      const preceding = shared.lock || Promise.resolve();
      let release;
      shared.lock = new Promise((resolve) => { release = resolve; });
      await preceding;
      try {
        if (signal.aborted) throw new DOMException("Stopped", "AbortError");
        return await callback();
      } finally { release(); }
    },
    lastAttempt: (account) => attempts.get(account) || 0,
    markAttempt: (account, time) => attempts.set(account, time),
    cooldown: (account) => cooldowns.get(account) || 0,
    setCooldown: (account, time) => cooldowns.set(account, time),
    hasReceipt: (target, mid) => receipts.has(`${target.account}:${target.peer}:${mid}`),
    saveReceipt: (target, mid) => receipts.add(`${target.account}:${target.peer}:${mid}`),
    send: async (peer, message) => sent.push({ peer, id: message.id, emoji: "👏" }),
  };
}

function message(overrides = {}) {
  return { _: "message", id: 123, mid: 4294967419, peerId: -10, fromId: 22,
    date: 1000, pFlags: {}, message: "0901234567 TH gửi ảnh", ...overrides };
}

function fixture(config = {}, adapter = fakeAdapter()) {
  const clock = { time: 1_000_000 };
  const sleeps = [];
  const monitor = new Monitor(adapter, () => {}, {
    now: () => clock.time,
    sleep: async (ms, signal) => {
      if (signal.aborted) throw new DOMException("Stopped", "AbortError");
      sleeps.push(ms);
      clock.time += ms;
      await new Promise(setImmediate);
    },
  });
  monitor.start({ interval: 1.5, dryRun: false, ...config });
  return { monitor, adapter, clock, sleeps };
}

async function drain(monitor) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (!monitor.draining && !monitor.queue.length) return;
    await new Promise(setImmediate);
  }
  throw new Error("Monitor did not finish its queue");
}

module.exports = { fakeAdapter, message, fixture, drain };
