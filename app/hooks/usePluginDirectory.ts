"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import type { PluginState } from "../lib/pluginDirectory";


type PluginSnapshot = { plugins: PluginState[] };

export function usePluginDirectory(accountId: string) {
  const [plugins, setPlugins] = useState<PluginState[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/plugins", { cache: "no-store" });
      const payload = await response.json() as PluginSnapshot & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Could not read plugins");
      setPlugins(payload.plugins);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not read plugins");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => void refresh());
    const onMessage = (event: MessageEvent) => {
      if (event.data?.type === "front-desk-plugin-connected" || event.data?.type === "front-desk-google-connected") void refresh();
    };
    window.addEventListener("message", onMessage);
    window.addEventListener("focus", refresh);
    return () => {
      window.cancelAnimationFrame(frame);
      window.removeEventListener("message", onMessage);
      window.removeEventListener("focus", refresh);
    };
  }, [accountId, refresh]);

  const request = useCallback(async (pluginId: string, action: "install" | "remove" | "disconnect") => {
    const path = action === "disconnect" ? `/api/plugins/${encodeURIComponent(pluginId)}/connect` : `/api/plugins/${encodeURIComponent(pluginId)}`;
    const response = await fetch(path, { method: action === "install" ? "POST" : "DELETE" });
    const payload = await response.json() as PluginSnapshot & { error?: string };
    if (!response.ok) throw new Error(payload.error || `Could not ${action} plugin`);
    setPlugins(payload.plugins);
    setError(undefined);
  }, []);

  const connect = useCallback(async (pluginId: string) => {
    const response = await fetch(`/api/plugins/${encodeURIComponent(pluginId)}/connect`, { method: "POST" });
    const payload = await response.json() as { authorization_url?: string; error?: string };
    if (!response.ok || !payload.authorization_url) throw new Error(payload.error || "Could not start plugin sign-in");
    const popup = window.open(payload.authorization_url, `front-desk-${pluginId}`, "popup,width=560,height=720");
    if (!popup) throw new Error("Allow pop-ups to connect this plugin");
    setError(undefined);
  }, []);

  const enabledIds = useMemo(() => new Set(plugins.filter((plugin) => plugin.connected).map((plugin) => plugin.id)), [plugins]);

  return {
    add: (pluginId: string) => request(pluginId, "install"),
    connect,
    disconnect: (pluginId: string) => request(pluginId, "disconnect"),
    enabledIds,
    error,
    loaded,
    plugins,
    refresh,
    remove: (pluginId: string) => request(pluginId, "remove"),
    setError,
  };
}
