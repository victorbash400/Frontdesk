import { Check, Circle, Play } from "lucide-react";

import type { OperatorTask } from "../types/task";
import styles from "./TaskRow.module.css";

type TaskRowProps = {
  clientName: string;
  selected: boolean;
  task: OperatorTask;
  onSelect: () => void;
};

export function TaskRow({ clientName, selected, task, onSelect }: TaskRowProps) {
  const StatusIcon = task.status === "completed" ? Check : task.status === "active" ? Play : Circle;
  return (
    <button aria-current={selected ? "page" : undefined} className={styles.row} data-status={task.status} onClick={onSelect} type="button">
      <span className={styles.marker}><StatusIcon aria-hidden="true" /></span>
      <span><strong>{task.text}</strong><small>{clientName} · {statusLabel(task.status)}</small></span>
    </button>
  );
}

function statusLabel(status: OperatorTask["status"]) {
  if (status === "active") return "Active";
  if (status === "completed") return "Completed";
  return "Ready";
}
