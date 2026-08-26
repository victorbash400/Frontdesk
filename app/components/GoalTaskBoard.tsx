import { Check, Circle, LoaderCircle, Pause, X } from "lucide-react";

import type { GoalAssignment } from "../types/goal";
import styles from "./GoalTaskBoard.module.css";

export function GoalTaskBoard({ tasks }: { tasks: GoalAssignment[] }) {
  const plannedTasks = tasks.filter((task) => task.title.trim());
  if (!plannedTasks.length) return null;
  return <ol aria-label="Goal task board" className={styles.board}>
    {plannedTasks.map((task) => <li data-state={task.status} key={task.id}>
      <span className={styles.marker}>{marker(task.status)}</span>
      <span className={styles.content}>
        <strong>{task.title}</strong>
        {task.currentStep && task.currentStep !== task.title ? <span className={styles.step}>{task.currentStep}</span> : null}
        {task.status === "running" ? <span aria-label={`${task.progress}% complete`} className={styles.progress}><i style={{ width: `${task.progress}%` }} /></span> : null}
        {task.nextStep ? <small>Next: {task.nextStep}</small> : null}
      </span>
    </li>)}
  </ol>;
}

function marker(status: string) {
  if (status === "running") return <LoaderCircle aria-hidden="true" />;
  if (status === "completed") return <Check aria-hidden="true" />;
  if (status === "failed") return <X aria-hidden="true" />;
  if (status === "blocked" || status === "cancelled") return <Pause aria-hidden="true" />;
  return <Circle aria-hidden="true" />;
}
