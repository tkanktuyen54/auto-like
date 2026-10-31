/* Isolated-world bridge. No Telegram message contents or credentials are exported. */
(function () {
  "use strict";
  const pending = new Map();
  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== location.origin || event.data?.source !== "autoclap-page-v1") return;
    const request = pending.get(event.data.id);
    if (!request) return;
    clearTimeout(request.timeout);
    pending.delete(event.data.id);
    request.respond(event.data.response);
  });
  chrome.runtime.onMessage.addListener((request, sender, respond) => {
    if (sender.id !== chrome.runtime.id || request?.type !== "AUTOCLAP_CONTROL") return;
    if (!["status", "start", "stop"].includes(request.action)) return;
    const id = crypto.randomUUID();
    const timeout = setTimeout(() => {
      pending.delete(id);
      respond({ ok: false, error: "Chưa kết nối được trang. Tải lại Telegram WebK rồi thử lại." });
    }, 5000);
    pending.set(id, { respond, timeout });
    window.postMessage({ source: "autoclap-extension-v1", id, action: request.action, config: request.config }, location.origin);
    return true;
  });
})();
