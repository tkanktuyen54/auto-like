const { test } = require("node:test");
const assert = require("node:assert/strict");
const { Adapter } = require("../chrome-extension/webk.js");

function fixture() {
  const calls = [];
  const handlers = new Map();
  const storage = new Map();
  const managers = {
    apiManager: { invokeApi: async (...args) => { calls.push(args); return { _: "updates", updates: [] }; } },
    appMessagesManager: { getMessageByPeer: async () => ({ message: "content" }) },
    appPeersManager: { getInputPeerById: async (peer) => ({ _: "inputPeerChannel", channel_id: Math.abs(peer), access_hash: "existing-session" }) },
    appMessagesIdsManager: { getMessageIdInfo: async (mid) => ({ messageId: mid % 4294967296 }) },
    apiUpdatesManager: { processUpdateMessage: async (updates) => calls.push(["update-ui", updates]) },
  };
  const window = {
    appImManager: { managers, chat: { peerId: -10, topbar: { title: { textContent: "Nhóm A" } } } },
    rootScope: { myId: 123, addEventListener: (event, callback) => handlers.set(event, callback),
      removeEventListener: (event) => handlers.delete(event) },
    navigator: { locks: { request: async (_name, _options, callback) => callback() } },
    localStorage: { getItem: (key) => storage.get(key) || null, setItem: (key, value) => storage.set(key, value) },
  };
  return { adapter: new Adapter(window), window, calls, handlers, storage, managers };
}

test("WebK adapter reads the current signed-in group without credentials", () => {
  const { adapter } = fixture();
  assert.deepEqual(adapter.context(), { ready: true, account: "123", peer: "-10", name: "Nhóm A", online: true });
});

test("WebK adapter reports login or chat selection required", () => {
  const { adapter, window } = fixture();
  delete window.appImManager.chat;
  assert.equal(adapter.context().ready, false);
  delete window.rootScope.myId;
  assert.equal(adapter.context().ready, false);
});

test("both new-message event formats subscribe and unsubscribe correctly", () => {
  const { adapter, handlers } = fixture();
  const received = [];
  const unsubscribe = adapter.subscribe((message) => received.push(message));
  handlers.get("history_append")({ message: { id: 1 } });
  handlers.get("history_multiappend")({ id: 2 });
  assert.deepEqual(received, [{ id: 1 }, { id: 2 }]);
  unsubscribe();
  assert.equal(handlers.size, 0);
});

test("reaction uses the server ID and current WebK managers, then applies updates", async () => {
  const { adapter, calls } = fixture();
  await adapter.send("-10", { mid: 4294967419 });
  assert.equal(calls[0][0], "messages.sendReaction");
  assert.equal(calls[0][1].msg_id, 123);
  assert.deepEqual(calls[0][1].reaction, [{ _: "reactionEmoji", emoticon: "👏" }]);
  assert.equal(calls[0][2].floodMaxTimeout, 0);
  assert.equal(calls[1][0], "update-ui");
});

test("server rejection propagates instead of reporting optimistic success", async () => {
  const { adapter, managers, calls } = fixture();
  managers.apiManager.invokeApi = async () => { throw { type: "REACTION_INVALID" }; };
  await assert.rejects(adapter.send("-10", { mid: 4294967419 }), (error) => error.type === "REACTION_INVALID");
  assert.equal(calls.length, 0);
});

test("switching group during message-ID lookup prevents the API mutation", async () => {
  const { adapter, managers, window, calls } = fixture();
  managers.appMessagesIdsManager.getMessageIdInfo = async () => {
    window.appImManager.chat.peerId = -20;
    return { messageId: 123 };
  };
  await assert.rejects(adapter.send("-10", { mid: 4294967419 }, "123"), (error) => error.type === "CONTEXT_CHANGED");
  assert.equal(calls.length, 0);
});

test("UI update failure cannot hide a successful server reaction", async () => {
  const { adapter, managers } = fixture();
  managers.apiUpdatesManager.processUpdateMessage = async () => { throw new Error("UI changed"); };
  await adapter.send("-10", { mid: 4294967419 });
});

test("receipts and pacing use only the extension's own namespaced localStorage", () => {
  const { adapter, storage } = fixture();
  const target = { account: "123", peer: "-10" };
  adapter.saveReceipt(target, 123);
  adapter.markAttempt("123", 1000);
  adapter.setCooldown("123", 5000);
  assert.equal(adapter.hasReceipt(target, 123), true);
  assert.equal(adapter.hasReceipt({ account: "456", peer: "-10" }, 123), false);
  assert.equal(adapter.lastAttempt("123"), 1000);
  assert.equal(adapter.cooldown("123"), 5000);
  for (const key of storage.keys()) assert.match(key, /^autoclap:/);
});
