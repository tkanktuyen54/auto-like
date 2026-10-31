/* MAIN-world endpoint: only local control/status crosses the isolated-world bridge. */
(function () {
  "use strict";
  if (window.__autoClapInstalled) return;
  window.__autoClapInstalled = true;
  const adapter = new AutoClapWebK.Adapter(window);
  const monitor = new AutoClapCore.Monitor(adapter);
  window.addEventListener("message", (event) => {
    if (event.source !== window || event.origin !== location.origin) return;
    const request = event.data;
    if (request?.source !== "autoclap-extension-v1" || typeof request.id !== "string") return;
    let response;
    try {
      if (request.action === "start") monitor.start(request.config || {});
      else if (request.action === "stop") monitor.stop();
      else if (request.action !== "status") return;
      response = { ok: true, context: adapter.context(), ...monitor.snapshot() };
    } catch (error) {
      response = { ok: false, error: error?.message || "Không thực hiện được thao tác." };
    }
    window.postMessage({ source: "autoclap-page-v1", id: request.id, response }, location.origin);
  });
  window.addEventListener("pagehide", () => monitor.stop());
})();
