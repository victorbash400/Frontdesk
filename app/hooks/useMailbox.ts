"use client";

import { useCallback, useEffect, useState } from "react";
import { authenticatedFetch } from "../lib/authenticatedFetch";
import type { MailboxState } from "../types/mailbox";

export function useMailbox() {
  const [mailbox, setMailbox] = useState<MailboxState>();
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    const response = await authenticatedFetch("/api/mailbox", { cache: "no-store" });
    const payload = await response.json() as MailboxState & { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not load the support inbox.");
    setMailbox(payload);
  }, []);

  useEffect(() => { const frame = requestAnimationFrame(() => void refresh().catch((reason) => setError(reason instanceof Error ? reason.message : "Could not load the support inbox."))); return () => cancelAnimationFrame(frame); }, [refresh]);

  const connect = useCallback(async (email: string, password: string) => {
    const response = await authenticatedFetch("/api/mailbox/titan/connect", { body: JSON.stringify({ email, password }), headers: { "Content-Type": "application/json" }, method: "POST" });
    const payload = await response.json() as MailboxState & { error?: string };
    if (!response.ok) throw new Error(payload.error || "Titan could not be connected.");
    setMailbox(payload); setError(undefined);
  }, []);

  const disconnect = useCallback(async () => {
    const response = await authenticatedFetch("/api/mailbox", { method: "DELETE" });
    if (!response.ok) throw new Error("Titan could not be disconnected.");
    await refresh();
  }, [refresh]);

  return { connect, disconnect, error, mailbox };
}
