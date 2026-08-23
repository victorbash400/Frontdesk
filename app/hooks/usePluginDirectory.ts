"use client";

import { useCallback, useEffect, useState } from "react";

const storageKey = "operator-plugin-directory-v1";

export function usePluginDirectory() {
  const [enabledIds, setEnabledIds] = useState<Set<string>>(new Set());
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        const stored = window.localStorage.getItem(storageKey);
        if (stored) {
          const ids: unknown = JSON.parse(stored);
          if (!Array.isArray(ids) || !ids.every((id) => typeof id === "string")) throw new Error("The saved plugin directory is invalid.");
          setEnabledIds(new Set(ids));
        }
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Could not load plugins.");
      } finally {
        setLoaded(true);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const toggle = useCallback((id: string) => {
    setEnabledIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        window.localStorage.setItem(storageKey, JSON.stringify([...next]));
        setError(undefined);
        return next;
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Could not save plugins.");
        return current;
      }
    });
  }, []);

  return { enabledIds, error, loaded, toggle };
}
