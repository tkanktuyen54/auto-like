/* Adapter for Telegram WebK. Uses its current session, never reads auth storage. */
(function (root) {
  "use strict";
  if (root.AutoClapWebK) return;
  const receiptsKey = "autoclap:reaction-receipts:v1";
  const coded = (type) => Object.assign(new Error(type), { type });

  class Adapter {
    constructor(windowObject = window) { this.window = windowObject; }
    objects() {
      const im = this.window.appImManager;
      const scope = this.window.rootScope;
      const managers = im?.managers;
      if (!im || !scope?.myId || !managers?.apiManager || !managers?.appMessagesManager) throw coded("ADAPTER_UNAVAILABLE");
      return { im, scope, managers };
    }
    context() {
      try {
        const { im, scope } = this.objects();
        const peer = im.chat?.peerId;
        if (!peer) return { ready: false, reason: "Đã đăng nhập. Hãy mở nhóm/kênh cần theo dõi." };
        if (!this.window.navigator.locks) return { ready: false, reason: "Cần Chrome 120 trở lên để chạy extension." };
        const name = im.chat.topbar?.title?.textContent?.trim() || `Nhóm ${peer}`;
        return { ready: true, account: String(scope.myId), peer: String(peer), name, online: !im.offline };
      } catch {
        return { ready: false, reason: "Đăng nhập Telegram WebK bằng QR, rồi mở nhóm cần theo dõi. Nếu đã đăng nhập, hãy tải lại trang." };
      }
    }
    subscribe(callback) {
      const { scope } = this.objects();
      const one = (payload) => callback(payload?.message);
      const multi = (message) => callback(message);
      scope.addEventListener("history_append", one);
      scope.addEventListener("history_multiappend", multi);
      return () => {
        scope.removeEventListener("history_append", one);
        scope.removeEventListener("history_multiappend", multi);
      };
    }
    async message(peer, mid) {
      return this.objects().managers.appMessagesManager.getMessageByPeer(Number(peer), mid);
    }
    withLock(account, signal, callback) {
      return this.window.navigator.locks.request(`autoclap:send:${account}`, { signal }, callback);
    }
    lastAttempt(account) {
      try { return Number(this.window.localStorage.getItem(`autoclap:last:${account}`)) || 0; }
      catch { return 0; }
    }
    markAttempt(account, timestamp) {
      this.window.localStorage.setItem(`autoclap:last:${account}`, String(timestamp));
    }
    cooldown(account) {
      return Number(this.window.localStorage.getItem(`autoclap:wait:${account}`)) || 0;
    }
    setCooldown(account, timestamp) {
      this.window.localStorage.setItem(`autoclap:wait:${account}`, String(timestamp));
    }
    receiptKey(target, mid) { return `${target.account}:${target.peer}:${mid}`; }
    receipts() {
      const entries = JSON.parse(this.window.localStorage.getItem(receiptsKey) || "[]");
      return Array.isArray(entries) ? entries.filter((entry) => typeof entry === "string").slice(-5000) : [];
    }
    hasReceipt(target, mid) { return this.receipts().includes(this.receiptKey(target, mid)); }
    saveReceipt(target, mid) {
      const entries = this.receipts();
      entries.push(this.receiptKey(target, mid));
      this.window.localStorage.setItem(receiptsKey, JSON.stringify([...new Set(entries)].slice(-5000)));
    }
    async send(peer, message, expectedAccount = this.context().account) {
      const { managers } = this.objects();
      // Use WebK's conversion helper; mid is not necessarily the Telegram server ID.
      const info = await managers.appMessagesIdsManager.getMessageIdInfo(message.mid);
      if (!Number.isSafeInteger(info?.messageId) || info.messageId <= 0) throw coded("MSG_ID_INVALID");
      const inputPeer = await managers.appPeersManager.getInputPeerById(Number(peer));
      const current = this.context();
      if (!current.ready || current.account !== expectedAccount || current.peer !== String(peer)) throw coded("CONTEXT_CHANGED");
      const updates = await managers.apiManager.invokeApi("messages.sendReaction", {
        peer: inputPeer,
        msg_id: info.messageId,
        reaction: [{ _: "reactionEmoji", emoticon: "👏" }],
      }, { floodMaxTimeout: 0, noErrorBox: true });
      // A failed UI refresh must not turn a server-confirmed reaction into a failed send.
      try { await managers.apiUpdatesManager.processUpdateMessage(updates); }
      catch { /* Telegram will reconcile through its update stream. */ }
    }
  }
  root.AutoClapWebK = Object.freeze({ Adapter });
  if (typeof module !== "undefined" && module.exports) module.exports = { Adapter };
})(globalThis);
