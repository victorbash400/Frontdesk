"use client";

import { useCallback, useEffect, useState } from "react";

import { loadTasks, saveTasks } from "../lib/taskStorage";
import type { OperatorTask, TaskStatus } from "../types/task";

export function useTasks() {
  const [tasks, setTasks] = useState<OperatorTask[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        setTasks(loadTasks());
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "Could not load tasks.");
      } finally {
        setLoaded(true);
      }
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const createTask = useCallback((clientId: string, text: string) => {
    const timestamp = new Date().toISOString();
    const task: OperatorTask = { id: crypto.randomUUID(), clientId, text: text.trim(), status: "ready", createdAt: timestamp, updatedAt: timestamp, startedAt: null, completedAt: null };
    const next = [task, ...tasks];
    saveTasks(next);
    setTasks(next);
    setError(undefined);
    return task;
  }, [tasks]);

  const updateTaskText = useCallback((id: string, text: string) => {
    const cleanText = text.trim();
    if (!cleanText) throw new Error("A task needs instructions.");
    const next = tasks.map((task) => task.id === id && task.status === "ready" ? { ...task, text: cleanText, updatedAt: new Date().toISOString() } : task);
    saveTasks(next);
    setTasks(next);
    setError(undefined);
  }, [tasks]);

  const setTaskStatus = useCallback((id: string, status: TaskStatus) => {
    const timestamp = new Date().toISOString();
    const next = tasks.map((task) => task.id === id ? {
      ...task,
      status,
      updatedAt: timestamp,
      startedAt: status === "active" ? timestamp : task.startedAt,
      completedAt: status === "completed" ? timestamp : null,
    } : task);
    saveTasks(next);
    setTasks(next);
    setError(undefined);
  }, [tasks]);

  return { createTask, error, loaded, setTaskStatus, tasks, updateTaskText };
}
