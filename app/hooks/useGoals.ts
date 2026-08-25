"use client";

import { useCallback, useEffect, useState } from "react";

import { authenticatedFetch } from "../lib/authenticatedFetch";
import type { GoalLiveUpdate, GoalStatus, OperatorGoal } from "../types/goal";

export function useGoals() {
  const [goals, setGoals] = useState<OperatorGoal[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();
  const [liveUpdates, setLiveUpdates] = useState<Record<string, GoalLiveUpdate>>({});

  const refresh = useCallback(async () => {
    try {
      const response = await authenticatedFetch("/api/goals", { cache: "no-store" });
      const payload = await response.json() as OperatorGoal[] | { error?: string };
      if (!response.ok) throw new Error(!Array.isArray(payload) && payload.error || "Could not load goals.");
      setGoals(payload as OperatorGoal[]);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load goals.");
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => { void refresh(); });
    const events = new EventSource("/api/events/stream");
    events.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type?: string; goal_id?: string; state?: GoalLiveUpdate["state"]; summary?: string };
      if (event.type === "goals_changed") void refresh();
      if (event.type === "goal_run" && event.goal_id && event.state) {
        setLiveUpdates((current) => ({ ...current, [event.goal_id as string]: { state: event.state as GoalLiveUpdate["state"], summary: event.summary } }));
        if (event.state !== "running") void refresh();
      }
    };
    return () => { window.cancelAnimationFrame(frame); events.close(); };
  }, [refresh]);

  const createGoal = useCallback(async (clientId: string, text: string, skillIds: string[], pluginIds: string[]) => {
    const goal = await requestGoal("/api/goals", { client_id: clientId, text, skill_ids: skillIds, plugin_ids: pluginIds }, "POST");
    setGoals((current) => [goal, ...current]);
    return goal;
  }, []);

  const updateGoal = useCallback(async (id: string, update: Pick<OperatorGoal, "text" | "skillIds" | "pluginIds">) => {
    const cleanText = update.text.trim();
    if (!cleanText) throw new Error("A goal needs instructions.");
    const current = goals.find((goal) => goal.id === id);
    const goal = await requestGoal(`/api/goals/${id}`, { text: cleanText, skill_ids: update.skillIds, plugin_ids: update.pluginIds, expected_version: current?.version }, "PATCH");
    setGoals((items) => items.map((item) => item.id === id ? goal : item));
  }, [goals]);

  const setGoalStatus = useCallback(async (id: string, status: GoalStatus) => {
    const goal = await requestGoal(`/api/goals/${id}`, { status }, "PATCH");
    setGoals((items) => items.map((item) => item.id === id ? goal : item));
  }, []);

  const deleteGoal = useCallback(async (id: string) => {
    const response = await authenticatedFetch(`/api/goals/${id}`, { method: "DELETE" });
    const payload = await response.json() as { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not delete goal.");
    setGoals((items) => items.filter((item) => item.id !== id));
    setLiveUpdates((current) => { const next = { ...current }; delete next[id]; return next; });
  }, []);

  const createAutomation = useCallback(async (id: string, instruction: string, intervalSeconds: number, timezone: string) => {
    const response = await authenticatedFetch(`/api/goals/${id}/automations`, { body: JSON.stringify({ instruction, interval_seconds: intervalSeconds, timezone }), headers: { "Content-Type": "application/json" }, method: "POST" });
    const payload = await response.json() as { error?: string };
    if (!response.ok) throw new Error(payload.error || "Could not create automation.");
    await refresh();
  }, [refresh]);

  return { createAutomation, createGoal, deleteGoal, error, goals, liveUpdates, loaded, refresh, setGoalStatus, updateGoal };
}

async function requestGoal(path: string, body: Record<string, unknown>, method: "POST" | "PATCH") {
  const response = await authenticatedFetch(path, { body: JSON.stringify(body), headers: { "Content-Type": "application/json" }, method });
  const payload = await response.json() as OperatorGoal | { error?: string };
  if (!response.ok) throw new Error("error" in payload && payload.error || "Could not save goal.");
  return payload as OperatorGoal;
}
