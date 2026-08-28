"use client";

import { useCallback, useEffect, useState } from "react";

import { authenticatedFetch } from "../lib/authenticatedFetch";
import type { OperatorSkill } from "../types/skill";

type SkillUpdate = Pick<OperatorSkill, "name" | "description" | "instructions" | "batchName" | "requiredPluginIds">;

export function useSkillsLibrary(_accountId: string) {
  const [skills, setSkills] = useState<OperatorSkill[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  const refresh = useCallback(async () => {
    try {
      const response = await authenticatedFetch("/api/skills", { cache: "no-store" });
      const payload = await response.json() as OperatorSkill[] | { error?: string };
      if (!response.ok || !Array.isArray(payload)) throw new Error(!Array.isArray(payload) && payload.error || "Could not load skills.");
      setSkills(payload);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load skills.");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => void refresh());
    return () => window.cancelAnimationFrame(frame);
  }, [refresh]);

  const createSkill = useCallback(async (name: string, description: string) => {
    const response = await authenticatedFetch("/api/skills", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, description, instructions: "", batch_name: "Created by you", required_plugin_ids: [] }) });
    const payload = await response.json() as OperatorSkill & { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not create the skill.");
    setSkills((current) => [...current, payload]);
    return payload.id;
  }, []);

  const updateSkill = useCallback(async (id: string, update: SkillUpdate) => {
    const response = await authenticatedFetch(`/api/skills/${encodeURIComponent(id)}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: update.name, description: update.description, instructions: update.instructions, batch_name: update.batchName, required_plugin_ids: update.requiredPluginIds }) });
    const payload = await response.json() as OperatorSkill & { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not update the skill.");
    setSkills((current) => current.map((skill) => skill.id === id ? payload : skill));
  }, []);

  const deleteSkill = useCallback(async (id: string) => {
    const response = await authenticatedFetch(`/api/skills/${encodeURIComponent(id)}`, { method: "DELETE" });
    const payload = await response.json() as { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not delete the skill.");
    setSkills((current) => current.filter((skill) => skill.id !== id));
  }, []);

  return { createSkill, deleteSkill, error, loaded, refresh, skills, updateSkill };
}
