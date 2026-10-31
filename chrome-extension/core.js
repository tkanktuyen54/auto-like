/* Shared filtering and queue logic. No Chrome or Telegram dependencies. */
(function (root) {
  "use strict";
  if (root.AutoClapCore) return;
  const separator = "[ .()\\-]*";
  const phonePattern = new RegExp(
    `(?<![\\p{L}\\p{N}_+])(?:0${separator}[35789]|(?:\\+?84|0084)${separator}[35789])` +
      `(?:${separator}[0-9]){8}(?![\\p{L}\\p{N}_])(?!${separator}[0-9])`, "u",
  );
  const escapeRegex = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  function evaluate(text, keyword = "care") {
    const normalized = String(text || "").normalize("NFC");
    const word = String(keyword || "").trim().normalize("NFC");
    if (!word || word.length > 100) return { matched: false, reason: "Nhập từ khóa từ 1 đến 100 ký tự." };
    const pattern = new RegExp(
      "(?<![\\p{L}\\p{N}_])" + word.split(/\s+/u).map(escapeRegex).join("\\s+") + "(?![\\p{L}\\p{N}_])", "iu",
    );
    if (!pattern.test(normalized)) return { matched: false, reason: `Không có từ khóa “${word}” đứng riêng.` };
    if (!phonePattern.test(normalized)) return { matched: false, reason: "Chưa có số di động Việt Nam hợp lệ (0… hoặc +84…)." };
    return { matched: true, reason: "Có số điện thoại và từ khóa. Tin này khớp điều kiện thả 👏." };
  }

  function pause(milliseconds, signal) {
    return new Promise((resolve, reject) => {
      if (signal.aborted) return reject(new DOMException("Stopped", "AbortError"));
      const abort = () => {
        clearTimeout(timer);
        reject(new DOMException("Stopped", "AbortError"));
      };
      const timer = setTimeout(() => {
        signal.removeEventListener("abort", abort);
        resolve();
      }, milliseconds);
      signal.addEventListener("abort", abort, { once: true });
    });
  }

  const emptyCounts = () => ({ matched: 0, sent: 0, preview: 0, skipped: 0, failed: 0 });
  function errorCode(error) {
    const candidate = error?.type || error?.code || "REQUEST_FAILED";
    return /^[A-Z][A-Z0-9_]{0,80}$/.test(String(candidate)) ? String(candidate) : "REQUEST_FAILED";
  }
  function describeError(error) {
    const code = errorCode(error);
    return ({
      REACTION_INVALID: "Nhóm chưa cho phép 👏 hoặc đã đạt giới hạn loại reaction.",
      CHAT_WRITE_FORBIDDEN: "Tài khoản không có quyền thả reaction trong nhóm này.",
      CHANNEL_PRIVATE: "Không còn truy cập được nhóm/kênh này.",
      MSG_ID_INVALID: "Tin nhắn đã xóa hoặc ID tin không còn hợp lệ.",
      AUTH_KEY_UNREGISTERED: "Phiên Telegram đã hết hiệu lực. Hãy đăng nhập lại Telegram Web.",
      SESSION_REVOKED: "Phiên đã bị thu hồi. Hãy đăng nhập lại Telegram Web.",
      ADAPTER_UNAVAILABLE: "Phiên bản Telegram WebK này chưa tương thích. Hãy tải lại trang.",
      CONTEXT_CHANGED: "Đã đổi nhóm hoặc tài khoản. Hãy bắt đầu lại ở nhóm cần theo dõi.",
    })[code] || `Chưa gửi được reaction (${code}).`;
  }

  class Monitor {
    constructor(adapter, onChange = () => {}, options = {}) {
      this.adapter = adapter;
      this.onChange = onChange;
      this.now = options.now || Date.now;
      this.sleep = options.sleep || pause;
      this.running = false;
      this.logs = [];
      this.counts = emptyCounts();
      this.queue = [];
      this.epoch = 0;
      this.waitUntil = 0;
      this.draining = null;
    }

    snapshot() {
      return {
        running: this.running,
        target: this.target || null,
        config: this.config || null,
        counts: { ...this.counts },
        queued: this.queue.length + (this.processing ? 1 : 0),
        waitUntil: this.waitUntil,
        logs: this.logs.slice(-60).reverse(),
      };
    }

    notify() { this.onChange(this.snapshot()); }
    log(level, message, messageId) {
      this.logs.push({ time: this.now(), level, message, messageId });
      if (this.logs.length > 100) this.logs.shift();
      this.notify();
    }

    sameContext(target = this.target) {
      const current = this.adapter.context();
      return current.ready && current.account === target.account && current.peer === target.peer;
    }

    start(config) {
      if (this.running) throw new Error("Hãy dừng lượt hiện tại trước khi bắt đầu lại.");
      const target = this.adapter.context();
      if (!target.ready) throw new Error(target.reason || "Đăng nhập Telegram WebK và mở nhóm trước.");
      if (!String(target.peer).startsWith("-")) throw new Error("Hãy mở một nhóm hoặc kênh để theo dõi.");
      const keyword = String(config.keyword || "").trim();
      if (!keyword || keyword.length > 100) throw new Error("Từ khóa cần từ 1 đến 100 ký tự.");
      const interval = Number(config.interval);
      if (!Number.isFinite(interval) || interval < 0.5 || interval > 60) throw new Error("Khoảng cách xử lý từ 0,5 đến 60 giây.");
      this.target = { account: target.account, peer: target.peer, name: target.name };
      this.config = { keyword, interval, dryRun: Boolean(config.dryRun) };
      this.startedAt = Math.floor(this.now() / 1000);
      this.controller = new AbortController();
      this.counts = emptyCounts();
      this.queue = [];
      this.seen = new Set();
      this.waitUntil = 0;
      this.processing = false;
      this.running = true;
      const epoch = ++this.epoch;
      try { this.unsubscribe = this.adapter.subscribe((message) => this.enqueue(message)); }
      catch (error) {
        this.running = false;
        this.controller.abort();
        throw error;
      }
      this.health = setInterval(() => {
        if (this.running && !this.sameContext()) this.stop("Đã đổi nhóm/tài khoản hoặc đăng xuất. Bấm Bắt đầu để chọn lại.");
      }, 1000);
      this.log("info", `${this.config.dryRun ? "Chạy thử" : "Tự thả 👏"} · ${target.name} · chỉ tin mới.`);
      return epoch;
    }

    eligible(message) {
      return message?._ === "message" && String(message.peerId) === this.target.peer &&
        !message.pFlags?.out && !message.out && String(message.fromId) !== this.target.account &&
        Number.isFinite(message.date) && message.date >= this.startedAt &&
        Number.isFinite(Number(message.mid)) && Number(message.mid) > 0 &&
        evaluate(message.message, this.config.keyword).matched;
    }

    enqueue(message) {
      if (!this.running) return false;
      if (!this.sameContext()) {
        this.stop("Đã đổi nhóm/tài khoản. Hãy bắt đầu lại ở nhóm cần theo dõi.");
        return false;
      }
      if (!this.eligible(message)) return false;
      const key = String(message.mid);
      if (this.seen.has(key)) return false;
      if (this.queue.length >= 1000) {
        this.counts.failed++;
        this.log("error", "Hàng đợi đầy; tin này chưa được xử lý.", message.id);
        return false;
      }
      this.seen.add(key);
      this.counts.matched++;
      // Queue only IDs; never save message bodies or phone numbers.
      this.queue.push({ mid: Number(message.mid), id: Number(message.id) });
      if (!this.draining) {
        const epoch = this.epoch;
        this.draining = this.drain(epoch).finally(() => {
          this.draining = null;
          // A new run may have queued a message while the previous RPC was finishing.
          if (this.running && this.queue.length) this.kick();
        });
      }
      this.notify();
      return true;
    }

    kick() {
      if (this.draining || !this.running) return;
      this.draining = this.drain(this.epoch).finally(() => {
        this.draining = null;
        if (this.running && this.queue.length) this.kick();
      });
    }

    async drain(epoch) {
      const signal = this.controller.signal;
      const target = this.target;
      const config = this.config;
      while (this.running && epoch === this.epoch && this.queue.length) {
        const item = this.queue.shift();
        this.processing = true;
        try {
          if (config.dryRun) {
            this.counts.preview++;
            this.log("preview", "Khớp bộ lọc · chạy thử, chưa gửi 👏.", item.id);
          } else {
            let done = false;
            while (!done && this.running && epoch === this.epoch) {
              try {
                const result = await this.adapter.withLock(target.account, signal, async () => {
                  if (signal.aborted || !this.sameContext(target)) throw { type: "CONTEXT_CHANGED" };
                  const last = this.adapter.lastAttempt(target.account);
                  const cooldown = this.adapter.cooldown(target.account);
                  const delay = Math.max(0, last + config.interval * 1000 - this.now(), cooldown - this.now());
                  if (cooldown > this.now()) {
                    this.waitUntil = cooldown;
                    this.notify();
                  }
                  if (delay) await this.sleep(delay, signal);
                  this.waitUntil = 0;
                  if (signal.aborted || !this.sameContext(target)) throw { type: "CONTEXT_CHANGED" };
                  if (this.adapter.hasReceipt(target, item.mid)) return "existing";
                  const fresh = await this.adapter.message(target.peer, item.mid);
                  if (signal.aborted || !this.sameContext(target)) throw { type: "CONTEXT_CHANGED" };
                  if (!fresh || !this.eligible(fresh)) return "changed";
                  const existing = fresh.reactions?.results?.some((reaction) =>
                    reaction.chosen_order !== undefined && reaction.chosen_order >= 0);
                  if (existing) return "existing";
                  this.adapter.markAttempt(target.account, this.now());
                  try { await this.adapter.send(target.peer, fresh, target.account); }
                  catch (error) {
                    const flood = /^FLOOD_(?:PREMIUM_)?WAIT_(\d+)$/.exec(errorCode(error));
                    if (flood) this.adapter.setCooldown(target.account, this.now() + (Number(flood[1]) + 1) * 1000);
                    throw error;
                  }
                  this.adapter.saveReceipt(target, item.mid);
                  return "sent";
                });
                if (epoch !== this.epoch) return;
                if (result === "sent") {
                  this.counts.sent++;
                  this.log("success", "Đã thả 👏", item.id);
                } else {
                  this.counts.skipped++;
                  this.log("info", result === "existing" ? "Đã xử lý hoặc bạn đã có reaction; giữ nguyên." : "Tin đã xóa hoặc không còn khớp bộ lọc.", item.id);
                }
                done = true;
              } catch (error) {
                const flood = /^FLOOD_(?:PREMIUM_)?WAIT_(\d+)$/.exec(errorCode(error));
                if (!flood) throw error;
                const seconds = Number(flood[1]) + 1;
                this.waitUntil = this.now() + seconds * 1000;
                this.log("waiting", `Telegram yêu cầu chờ ${seconds} giây; sẽ tự tiếp tục.`, item.id);
                await this.sleep(seconds * 1000, signal);
                this.waitUntil = 0;
              }
            }
          }
        } catch (error) {
          if (error?.name === "AbortError" || signal.aborted || epoch !== this.epoch) return;
          this.counts.failed++;
          this.log("error", describeError(error), item.id);
          if (["CONTEXT_CHANGED", "AUTH_KEY_UNREGISTERED", "SESSION_REVOKED", "ADAPTER_UNAVAILABLE"].includes(errorCode(error))) {
            this.stop("Đã dừng. Kiểm tra phiên đăng nhập rồi bắt đầu lại.");
          }
        } finally {
          if (epoch === this.epoch) {
            this.processing = false;
            this.notify();
          }
        }
      }
    }

    stop(reason = "Đã dừng theo dõi; hàng đợi đã được hủy.") {
      const wasRunning = this.running;
      this.running = false;
      this.epoch++;
      this.controller?.abort();
      this.unsubscribe?.();
      clearInterval(this.health);
      this.queue = [];
      this.processing = false;
      this.waitUntil = 0;
      if (wasRunning) this.log("info", reason);
      this.notify();
    }
  }

  const api = Object.freeze({ evaluate, pause, Monitor, describeError });
  root.AutoClapCore = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(globalThis);
