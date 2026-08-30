"use client";

import { useCallback, useEffect, useState } from "react";

import { authenticatedFetch } from "../lib/authenticatedFetch";
import type { MailThread } from "../types/mail";

export function useMailboxThreads(connected: boolean) {
  const [threads, setThreads] = useState<MailThread[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    if (!connected) {
      setThreads([]);
      setLoaded(true);
      return;
    }
    try {
      const response = await authenticatedFetch("/api/mailbox/threads", { cache: "no-store" });
      const payload = await response.json() as MailThread[] | { error?: string };
      if (!response.ok) throw new Error(!Array.isArray(payload) && payload.error || "Could not load customer email.");
      setThreads(payload as MailThread[]);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load customer email.");
    } finally {
      setLoaded(true);
    }
  }, [connected]);

  const retry = useCallback(async (messageId: string) => {
    const response = await authenticatedFetch(`/api/mailbox/messages/${encodeURIComponent(messageId)}/retry`, { method: "POST" });
    const payload = await response.json() as { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not retry the Email Agent.");
    await refresh();
  }, [refresh]);

  useEffect(() => {
    const frame = requestAnimationFrame(() => void refresh());
    if (!connected) return () => cancelAnimationFrame(frame);
    const events = new EventSource("/api/events/stream");
    events.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type?: string };
      if (event.type === "mailbox_changed") void refresh();
    };
    return () => { cancelAnimationFrame(frame); events.close(); };
  }, [connected, refresh]);

  return { error, loaded, refresh, retry, threads };
}
