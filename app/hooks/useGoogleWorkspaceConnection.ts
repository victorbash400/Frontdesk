"use client";

import { useCallback, useEffect, useState } from "react";

import { authenticatedFetch } from "../lib/authenticatedFetch";

export type WorkspacePermission = { id: string; name: string; description: string; enabled: boolean };
type ConnectionState = {
  configured: boolean;
  connected: boolean;
  needs_reconnect: boolean;
  missing_scopes: string[];
  email?: string | null;
  name?: string | null;
  picture?: string | null;
  permissions: WorkspacePermission[];
};

const emptyState: ConnectionState = {
  configured: false,
  connected: false,
  needs_reconnect: false,
  missing_scopes: [],
  permissions: [],
};

export function useGoogleWorkspaceConnection() {
  const [state, setState] = useState<ConnectionState>(emptyState);
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    try {
      const response = await authenticatedFetch("/api/plugins/google", { cache: "no-store" });
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
    const response = await authenticatedFetch("/api/plugins/google", { method: "POST" });
    const payload = await response.json() as { authorization_url?: string; error?: string };
    if (!response.ok || !payload.authorization_url) throw new Error(payload.error || "Could not start Google sign-in");
    const authorizationTab = window.open(payload.authorization_url, "_blank");
    if (!authorizationTab) throw new Error("Allow new tabs to connect Google Workspace");
  }, []);

  const disconnect = useCallback(async () => {
    const response = await authenticatedFetch("/api/plugins/google", { method: "DELETE" });
    const payload = await response.json() as { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not disconnect Google Workspace");
    await refresh();
  }, [refresh]);

  const setPermission = useCallback(async (permissionId: string, enabled: boolean) => {
    const response = await authenticatedFetch(`/api/plugins/google/permissions/${encodeURIComponent(permissionId)}`, {
      body: JSON.stringify({ enabled }),
      headers: { "Content-Type": "application/json" },
      method: "PUT",
    });
    const payload = await response.json() as ConnectionState & { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not update the Workspace permission");
    setState(payload);
  }, []);

  return { ...state, connect, disconnect, error, refresh, setError, setPermission };
}
