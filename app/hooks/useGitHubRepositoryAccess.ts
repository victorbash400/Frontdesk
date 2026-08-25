"use client";

import { useCallback, useEffect, useState } from "react";


export type GitHubRepository = {
  full_name: string;
  private: boolean;
};

type RepositoryAccess = {
  repositories: GitHubRepository[];
  selected: string[];
};

export function useGitHubRepositoryAccess(onSaved: () => void) {
  const [repositories, setRepositories] = useState<GitHubRepository[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loaded, setLoaded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string>();

  const load = useCallback(async () => {
    try {
      const response = await fetch("/api/plugins/github/repositories", { cache: "no-store" });
      const payload = await response.json() as RepositoryAccess & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Could not load GitHub repositories");
      setRepositories(payload.repositories);
      setSelected(new Set(payload.selected));
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load GitHub repositories");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => void load());
    return () => window.cancelAnimationFrame(frame);
  }, [load]);

  const save = useCallback(async () => {
    setSaving(true);
    try {
      const response = await fetch("/api/plugins/github/repositories", {
        method: "PUT",
        body: JSON.stringify({ repositories: [...selected] }),
        headers: { "Content-Type": "application/json" },
      });
      const payload = await response.json() as RepositoryAccess & { error?: string };
      if (!response.ok) throw new Error(payload.error || "Could not save repository access");
      setRepositories(payload.repositories);
      setSelected(new Set(payload.selected));
      setError(undefined);
      onSaved();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save repository access");
    } finally {
      setSaving(false);
    }
  }, [onSaved, selected]);

  const toggle = useCallback((fullName: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(fullName)) next.delete(fullName);
      else next.add(fullName);
      return next;
    });
  }, []);

  return { error, loaded, repositories, save, saving, selected, setSelected, toggle };
}
