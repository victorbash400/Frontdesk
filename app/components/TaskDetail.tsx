"use client";

import { Check, Play, RotateCcw } from "lucide-react";
import { useState } from "react";

import type { OperatorTask, TaskStatus } from "../types/task";
import styles from "./TaskDetail.module.css";

type TaskDetailProps = {
  clientName: string;
  task: OperatorTask;
  onStatusChange: (status: TaskStatus) => void;
  onTextSave: (text: string) => void;
};

export function TaskDetail({ clientName, task, onStatusChange, onTextSave }: TaskDetailProps) {
  const [text, setText] = useState(task.text);
  const [error, setError] = useState<string>();
  const editable = task.status === "ready";

  function save() {
    try {
      onTextSave(text);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this task.");
    }
  }

  function changeStatus(status: TaskStatus) {
    try {
      onStatusChange(status);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not update this task.");
    }
  }

  return (
    <article className={styles.detail}>
      <header><span><strong>{clientName}</strong><small>{statusLabel(task.status)}</small></span>{task.status === "ready" ? <button className={styles.primary} onClick={() => changeStatus("active")} type="button"><Play aria-hidden="true" />Start Task</button> : null}{task.status === "active" ? <button className={styles.primary} onClick={() => changeStatus("completed")} type="button"><Check aria-hidden="true" />End Task</button> : null}{task.status === "completed" ? <button onClick={() => changeStatus("ready")} type="button"><RotateCcw aria-hidden="true" />Reopen</button> : null}</header>
      <textarea aria-label="Task text" onChange={(event) => { setText(event.target.value); setError(undefined); }} readOnly={!editable} spellCheck="true" value={text} />
      <footer>{error ? <small role="alert">{error}</small> : <small>Created {formatDate(task.createdAt)}</small>}{editable ? <button disabled={text.trim() === task.text || !text.trim()} onClick={save} type="button">Save</button> : null}</footer>
    </article>
  );
}

function statusLabel(status: OperatorTask["status"]) {
  if (status === "active") return "Active";
  if (status === "completed") return "Completed";
  return "Ready";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
