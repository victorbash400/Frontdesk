"use client";

import { useCallback, useEffect, useState } from "react";

import { authenticatedFetch } from "../lib/authenticatedFetch";
import type { ClientNotification } from "./useClientNotifications";

export function useGoalQuestions() {
  const [questions, setQuestions] = useState<ClientNotification[]>([]);
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    try {
      const response = await authenticatedFetch("/api/notifications?open_questions=true", { cache: "no-store" });
      const payload = await response.json() as ClientNotification[] | { error?: string };
      if (!response.ok) throw new Error(!Array.isArray(payload) && payload.error || "Could not load questions.");
      setQuestions((payload as ClientNotification[]).filter((item) => item.kind === "clarification" && item.status === "open"));
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load questions.");
    }
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => { void refresh(); });
    const events = new EventSource("/api/events/stream");
    events.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type?: string };
      if (event.type === "notifications_changed") void refresh();
    };
    return () => { window.cancelAnimationFrame(frame); events.close(); };
  }, [refresh]);

  const answer = useCallback(async (id: string, value: string) => {
    const response = await authenticatedFetch(`/api/notifications/${id}/answer`, {
      body: JSON.stringify({ answer: value }),
      headers: { "Content-Type": "application/json" },
      method: "POST",
    });
    const payload = await response.json() as ClientNotification | { error?: string };
    if (!response.ok) throw new Error("error" in payload && payload.error || "Could not answer question.");
    setQuestions((items) => items.filter((item) => item.id !== id));
  }, []);

  return { answer, error, questions };
}
