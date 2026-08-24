"use client";

import { useCallback, useEffect, useState } from "react";

import { loadGoals, saveGoals } from "../lib/goalStorage";
import type { GoalStatus, OperatorGoal } from "../types/goal";

export function useGoals(accountId: string) {
  const [goals, setGoals] = useState<OperatorGoal[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        setGoals(loadGoals(accountId));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Could not load goals.");
      } finally {
        setLoaded(true);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, [accountId]);

  const createGoal = useCallback((clientId: string, text: string, skillIds: string[], pluginIds: string[]) => {
    const timestamp = new Date().toISOString();
    const goal: OperatorGoal = { id: crypto.randomUUID(), clientId, text: text.trim(), skillIds, pluginIds, status: "active", createdAt: timestamp, updatedAt: timestamp, startedAt: timestamp, completedAt: null };
    const next = [goal, ...goals];
    saveGoals(accountId, next);
    setGoals(next);
    setError(undefined);
    return goal;
  }, [accountId, goals]);

  const updateGoal = useCallback((id: string, update: Pick<OperatorGoal, "text" | "skillIds" | "pluginIds">) => {
    const cleanText = update.text.trim();
    if (!cleanText) throw new Error("A goal needs instructions.");
    const next = goals.map((goal) => goal.id === id ? { ...goal, ...update, text: cleanText, updatedAt: new Date().toISOString() } : goal);
    saveGoals(accountId, next);
    setGoals(next);
    setError(undefined);
  }, [accountId, goals]);

  const setGoalStatus = useCallback((id: string, status: GoalStatus) => {
    const timestamp = new Date().toISOString();
    const next = goals.map((goal) => goal.id === id ? {
      ...goal,
      status,
      updatedAt: timestamp,
      startedAt: status === "active" ? timestamp : goal.startedAt,
      completedAt: status === "completed" ? timestamp : null,
    } : goal);
    saveGoals(accountId, next);
    setGoals(next);
    setError(undefined);
  }, [accountId, goals]);

  return { createGoal, error, goals, loaded, setGoalStatus, updateGoal };
}
