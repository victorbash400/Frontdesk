import type { OperatorTask } from "../types/task";
import { accountStorageKey } from "./accountStorage";

const storageNamespace = "front-desk-tasks-v1";

export function loadTasks(accountId: string): OperatorTask[] {
  const stored = window.localStorage.getItem(accountStorageKey(storageNamespace, accountId));
  if (!stored) return [];
  const value: unknown = JSON.parse(stored);
  if (!Array.isArray(value) || !value.every(isTask)) throw new Error("The saved tasks are invalid.");
  return value;
}

export function saveTasks(accountId: string, tasks: OperatorTask[]) {
  window.localStorage.setItem(accountStorageKey(storageNamespace, accountId), JSON.stringify(tasks));
}

function isTask(value: unknown): value is OperatorTask {
  if (!value || typeof value !== "object") return false;
  const task = value as Partial<OperatorTask>;
  return typeof task.id === "string" && typeof task.clientId === "string" && typeof task.text === "string" && ["ready", "active", "completed"].includes(task.status ?? "") && typeof task.createdAt === "string" && typeof task.updatedAt === "string" && (task.startedAt === null || typeof task.startedAt === "string") && (task.completedAt === null || typeof task.completedAt === "string");
}
