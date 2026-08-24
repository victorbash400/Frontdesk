import type { OperatorGoal } from "../types/goal";
import { accountStorageKey } from "./accountStorage";

const storageNamespace = "front-desk-goals-v1";

export function loadGoals(accountId: string): OperatorGoal[] {
  const key = accountStorageKey(storageNamespace, accountId);
  const stored = window.localStorage.getItem(key);
  if (!stored) return [];
  const value: unknown = JSON.parse(stored);
  if (!Array.isArray(value)) throw new Error("The saved goals are invalid.");
  const goals = value.map(normalizeGoal);
  if (!goals.every(isGoal)) throw new Error("The saved goals are invalid.");
  return goals;
}

export function saveGoals(accountId: string, goals: OperatorGoal[]) {
  window.localStorage.setItem(accountStorageKey(storageNamespace, accountId), JSON.stringify(goals));
}

function isGoal(value: unknown): value is OperatorGoal {
  if (!value || typeof value !== "object") return false;
  const goal = value as Partial<OperatorGoal>;
  return typeof goal.id === "string" && typeof goal.clientId === "string" && typeof goal.text === "string" && isStringArray(goal.skillIds) && isStringArray(goal.pluginIds) && ["ready", "active", "completed"].includes(goal.status ?? "") && typeof goal.createdAt === "string" && typeof goal.updatedAt === "string" && (goal.startedAt === null || typeof goal.startedAt === "string") && (goal.completedAt === null || typeof goal.completedAt === "string");
}

function normalizeGoal(value: unknown) {
  if (!value || typeof value !== "object") return value;
  const goal = value as Partial<OperatorGoal>;
  return { ...goal, skillIds: goal.skillIds ?? [], pluginIds: goal.pluginIds ?? [] };
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}
