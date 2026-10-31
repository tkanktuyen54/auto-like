"use strict";
const byId = (id) => document.getElementById(id);
const configFields = ["keyword", "interval", "dry-run"];
let tabId = null;
let busy = false;
let requesting = false;
let lastState = null;

function notice(message) {
  byId("notice").textContent = message || "";
  byId("notice").hidden = !message;
}

function config() {
  return { keyword: byId("keyword").value.trim(), interval: Number(byId("interval").value), dryRun: byId("dry-run").checked };
}

function preview() {
  const result = AutoClapCore.evaluate(byId("preview").value, byId("keyword").value);
  byId("preview-result").textContent = `${result.matched ? "✓" : "○"} ${result.reason}`;
  byId("preview-result").classList.toggle("match", result.matched);
}

function render(state) {
  lastState = state;
  const context = state.context || {};
  const running = Boolean(state.running);
  byId("badge").textContent = running ? (state.config?.dryRun ? "● Chạy thử" : "● Theo dõi") : context.ready ? "● Sẵn sàng" : "Chưa kết nối";
  byId("badge").classList.toggle("active", running);
  byId("chat-name").textContent = running ? state.target.name : context.name || "Mở nhóm trên Telegram WebK";
  byId("connection-note").textContent = context.ready
    ? "Dùng phiên Telegram Web hiện tại · không cần API ID/Hash."
    : context.reason || "Đăng nhập bằng QR rồi mở một nhóm để bắt đầu.";
  byId("start").disabled = busy || running || !context.ready || !String(context.peer).startsWith("-");
  byId("stop").disabled = busy || !running;
  for (const id of configFields) byId(id).disabled = busy || running;
  if (running && state.config) {
    byId("keyword").value = state.config.keyword;
    byId("interval").value = state.config.interval;
    byId("dry-run").checked = state.config.dryRun;
  }
  for (const key of ["matched", "sent", "failed"]) byId(key).textContent = String(state.counts?.[key] || 0);
  byId("preview-count").textContent = String(state.counts?.preview || 0);
  byId("queue").textContent = `Chờ: ${state.queued || 0}`;
  const wait = Math.max(0, Math.ceil(((state.waitUntil || 0) - Date.now()) / 1000));
  byId("run-note").textContent = wait > 0 ? `Telegram yêu cầu chờ · còn khoảng ${wait} giây.` : running
    ? "Đang nghe tin mới. Đóng popup này vẫn tiếp tục chạy trong tab."
    : "Chỉ tin mới từ lúc Bắt đầu · giữ nguyên reaction bạn đã thả.";
  const logs = byId("logs");
  logs.replaceChildren();
  if (!state.logs?.length) {
    const item = document.createElement("li");
    item.className = "empty";
    item.textContent = "Chưa có hoạt động.";
    logs.append(item);
  }
  for (const entry of (state.logs || []).slice(0, 60)) {
    const item = document.createElement("li");
    if (["success", "error", "waiting", "info", "preview"].includes(entry.level)) item.className = entry.level;
    const timestamp = document.createElement("time");
    timestamp.textContent = new Date(entry.time).toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    const text = document.createElement("span");
    text.textContent = String(entry.message).slice(0, 500) + (entry.messageId ? ` · #${entry.messageId}` : "");
    item.append(timestamp, text);
    logs.append(item);
  }
}

async function request(action, options = {}) {
  if (tabId === null) return { ok: false, error: "Mở Telegram WebK trước khi bắt đầu." };
  try { return await chrome.tabs.sendMessage(tabId, { type: "AUTOCLAP_CONTROL", action, ...options }); }
  catch { return { ok: false, error: "Hãy tải lại tab Telegram WebK sau khi nạp extension, rồi mở lại popup." }; }
}

async function refresh() {
  if (busy || requesting || tabId === null) return;
  requesting = true;
  try {
    const state = await request("status");
    if (state?.ok) render(state);
    else notice(state?.error);
  } finally { requesting = false; }
}

async function control(action) {
  if (busy) return;
  busy = true;
  if (lastState) render(lastState);
  notice("");
  try {
    const settings = config();
    if (action === "start") await chrome.storage.local.set({ autoClapSettings: settings });
    const state = await request(action, { config: settings });
    busy = false;
    if (state?.ok) render(state);
    else {
      if (lastState) render(lastState);
      notice(state?.error || "Không thực hiện được thao tác.");
    }
  } catch {
    busy = false;
    if (lastState) render(lastState);
    notice("Không lưu được cấu hình extension. Hãy kiểm tra Chrome rồi thử lại.");
  }
}

byId("start").addEventListener("click", () => control("start"));
byId("stop").addEventListener("click", () => control("stop"));
byId("open-telegram").addEventListener("click", () => chrome.tabs.create({ url: "https://web.telegram.org/k/" }));
byId("preview").addEventListener("input", preview);
byId("keyword").addEventListener("input", preview);

async function initialize() {
  try {
    const saved = (await chrome.storage.local.get("autoClapSettings")).autoClapSettings;
    if (saved && typeof saved.keyword === "string") {
      byId("keyword").value = saved.keyword;
      if (Number.isFinite(saved.interval) && saved.interval >= 0.5 && saved.interval <= 60) byId("interval").value = saved.interval;
      byId("dry-run").checked = Boolean(saved.dryRun);
    }
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tab?.url?.startsWith("https://web.telegram.org/k/")) {
      tabId = tab.id;
      await refresh();
    } else {
      render({ context: { ready: false, reason: "Mở Telegram WebK (đường dẫn /k/), đăng nhập bằng QR rồi chọn nhóm." } });
    }
  } catch { notice("Không đọc được cấu hình. Đóng popup rồi mở lại để thử."); }
  preview();
  setInterval(refresh, 1200);
}
initialize();
