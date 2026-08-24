"use client";

import { useCallback, useEffect, useState } from "react";


type ConnectionState = { configured: boolean; connected: boolean; email?: string | null };

export function useGoogleWorkspaceConnection() {
  const [state, setState] = useState<ConnectionState>({ configured: false, connected: false });
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/plugins/google", { cache: "no-store" });
      const payload = await response.json() as ConnectionState & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Could not read the Google Workspace connection");
      setState(payload);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not read the Google Workspace connection");
    }
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => void refresh());
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === "front-desk-google-connected") void refresh();
    };
    window.addEventListener("message", onMessage);
    window.addEventListener("focus", refresh);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("message", onMessage);
      window.removeEventListener("focus", refresh);
    };
  }, [refresh]);

  const connect = useCallback(async () => {
    const response = await fetch("/api/plugins/google", { method: "POST" });
    const payload = await response.json() as { authorization_url?: string; error?: string };
    if (!response.ok || !payload.authorization_url) throw new Error(payload.error || "Could not start Google sign-in");
    const popup = window.open(payload.authorization_url, "front-desk-google", "popup,width=560,height=720");
    if (!popup) throw new Error("Allow pop-ups to connect Google Workspace");
  }, []);

  const disconnect = useCallback(async () => {
    const response = await fetch("/api/plugins/google", { method: "DELETE" });
    const payload = await response.json() as { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not disconnect Google Workspace");
    await refresh();
  }, [refresh]);

  return { ...state, connect, disconnect, error, refresh };
}
