"use client";

import { useEffect } from "react";


export function useCloudBrowserBridge() {
  useEffect(() => {
    const controller = new AbortController();
    void navigator.locks.request("front-desk-browser-relay", { signal: controller.signal }, async () => {
      if (controller.signal.aborted) return;
      const events = new EventSource("/api/events/stream");
      events.onmessage = (message) => {
        const event = JSON.parse(message.data) as { type?: string; relay_url?: string };
        if (event.type === "browser_connection_requested" && event.relay_url) {
          window.postMessage({ type: "frontDeskCloudConnect", relayUrl: event.relay_url }, window.location.origin);
        }
      };
      await new Promise<void>((resolve) => controller.signal.addEventListener("abort", () => resolve(), { once: true }));
      events.close();
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) console.error("Front Desk browser relay failed", error);
    });
    return () => controller.abort();
  }, []);
}
