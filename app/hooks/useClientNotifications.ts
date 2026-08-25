"use client";

import { useCallback, useEffect, useState } from "react";

import { authenticatedFetch } from "../lib/authenticatedFetch";

export type ClientNotification = { id: string; goalId: string; clientId: string; kind: "clarification" | "message"; message: string; status: "open" | "answered"; answer: string | null; createdAt: string; answeredAt: string | null };

export function useClientNotifications(clientId: string) {
  const [notifications, setNotifications] = useState<ClientNotification[]>([]);
  const [error, setError] = useState<string>();
  const refresh = useCallback(async () => {
    try {
      const response = await authenticatedFetch(`/api/notifications?client_id=${encodeURIComponent(clientId)}`, { cache: "no-store" });
      const payload = await response.json() as ClientNotification[] | { error?: string };
      if (!response.ok) throw new Error(!Array.isArray(payload) && payload.error || "Could not load notifications.");
      setNotifications(payload as ClientNotification[]);
      setError(undefined);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load notifications."); }
  }, [clientId]);
  useEffect(() => {
    const frame = window.requestAnimationFrame(() => { void refresh(); });
    const events = new EventSource("/api/events/stream");
    events.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type?: string; client_id?: string };
      if (event.type === "notifications_changed" && event.client_id === clientId) void refresh();
    };
    return () => { window.cancelAnimationFrame(frame); events.close(); };
  }, [clientId, refresh]);
  const answer = useCallback(async (id: string, value: string) => {
    const response = await authenticatedFetch(`/api/notifications/${id}/answer`, { body: JSON.stringify({ answer: value }), headers: { "Content-Type": "application/json" }, method: "POST" });
    const payload = await response.json() as ClientNotification | { error?: string };
    if (!response.ok) throw new Error("error" in payload && payload.error || "Could not answer clarification.");
    setNotifications((items) => items.map((item) => item.id === id ? payload as ClientNotification : item));
  }, []);
  return { answer, error, notifications, refresh };
}
