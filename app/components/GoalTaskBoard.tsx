import type { GoalAssignment } from "../types/goal";
import styles from "./GoalTaskBoard.module.css";

export function GoalTaskBoard({ runtimeOnline, tasks }: { runtimeOnline: boolean; tasks: GoalAssignment[] }) {
  const orderedTasks = tasks
    .filter((task) => task.title.trim())
    .toSorted((left, right) => left.createdAt.localeCompare(right.createdAt));
  const lines = orderedTasks.flatMap((task) => {
    const updates = task.updates
      .filter((update) => update.message.trim())
      .toSorted((left, right) => left.createdAt.localeCompare(right.createdAt))
      .filter((update, index, items) => items.findIndex((item) => item.message.trim() === update.message.trim()) === index);
    const taskLine = { id: task.id, message: task.title, active: runtimeOnline && task.status === "running" && !updates.length };
    return [taskLine, ...updates.map((update, index) => ({
      id: update.id,
      message: update.message,
      active: runtimeOnline && task.status === "running" && index === updates.length - 1,
    }))];
  });
  if (!lines.length) return null;
  return <ol aria-label="Goal task board" className={styles.board}>
    {lines.map((line) => <li data-active={line.active || undefined} key={line.id}>{line.message}</li>)}
  </ol>;
}
