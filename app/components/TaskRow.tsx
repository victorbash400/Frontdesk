import { Check, ChevronDown, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import type { OperatorTask } from "../types/task";
import styles from "./TaskRow.module.css";

type TaskRowProps = {
  clientName: string;
  detail: ReactNode;
  expanded: boolean;
  task: OperatorTask;
  onSelect: () => void;
};

export function TaskRow({ clientName, detail, expanded, task, onSelect }: TaskRowProps) {
  return (
    <article className={styles.row} data-expanded={expanded} data-status={task.status}>
      <button aria-expanded={expanded} aria-label={`${task.text}, ${statusLabel(task.status)}`} onClick={onSelect} type="button">
        <span className={styles.marker}>{task.status === "completed" ? <Check aria-hidden="true" /> : task.status === "active" ? <LoaderCircle aria-hidden="true" /> : null}</span>
        <span className={styles.copy}><strong>{task.text}</strong><small>{clientName} · {statusLabel(task.status)}</small></span>
        <ChevronDown aria-hidden="true" className={styles.chevron} />
      </button>
      <section aria-hidden={!expanded} className={styles.reveal} inert={!expanded ? true : undefined}><span>{detail}</span></section>
    </article>
  );
}

function statusLabel(status: OperatorTask["status"]) {
  if (status === "active") return "Active";
  if (status === "completed") return "Completed";
  return "Ready";
}
