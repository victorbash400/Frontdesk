import type { GoalActivity, GoalAssignment, GoalLiveUpdate } from "../types/goal";
import styles from "./GoalActivityList.module.css";

export function GoalActivityList({ activities, assignments, liveUpdate }: { activities: GoalActivity[]; assignments: GoalAssignment[]; liveUpdate?: GoalLiveUpdate }) {
  const latestAssignment = assignments[0];
  const currentActivities = latestAssignment
    ? activities.filter((item) => item.createdAt >= latestAssignment.createdAt)
    : [];
  const updates = [
    ...(liveUpdate?.summary ? [{ id: "live", message: liveUpdate.summary, live: liveUpdate.state === "queued" || liveUpdate.state === "running" }] : []),
    ...(latestAssignment?.report.trim() ? [{ id: latestAssignment.id, message: latestAssignment.report }] : []),
    ...currentActivities.filter((item) => ["worker_update", "run_completed", "run_failed"].includes(item.kind)).map((item) => ({ id: item.id, message: item.summary })),
  ].filter((item, index, items) => item.message.trim() && items.findIndex((candidate) => candidate.message.trim() === item.message.trim()) === index).slice(0, 12);
  return updates.length ? <ol aria-label="Goal updates" className={styles.updates}>{updates.map((update) => <li data-live={"live" in update && update.live || undefined} key={update.id}>{update.message}</li>)}</ol> : null;
}
