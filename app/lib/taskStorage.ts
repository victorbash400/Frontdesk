import type { OperatorTask } from "../types/task";

const storageKey = "operator-tasks-v1";

export function loadTasks(): OperatorTask[] {
  const stored = window.localStorage.getItem(storageKey);
  if (!stored) return [];
  const value: unknown = JSON.parse(stored);
  if (!Array.isArray(value) || !value.every(isTask)) throw new Error("The saved tasks are invalid.");
  return value;
}

export function saveTasks(tasks: OperatorTask[]) {
  window.localStorage.setItem(storageKey, JSON.stringify(tasks));
}

function isTask(value: unknown): value is OperatorTask {
  if (!value || typeof value !== "object") return false;
  const task = value as Partial<OperatorTask>;
  return typeof task.id === "string" && typeof task.clientId === "string" && typeof task.text === "string" && ["ready", "active", "completed"].includes(task.status ?? "") && typeof task.createdAt === "string" && typeof task.updatedAt === "string" && (task.startedAt === null || typeof task.startedAt === "string") && (task.completedAt === null || typeof task.completedAt === "string");
}
