import type { GoalLiveUpdate, OperatorGoal } from "../types/goal";
import { GoalWorkPreview } from "./GoalWorkPreview";
import styles from "./GoalPreviewPane.module.css";

export function GoalPreviewPane({ goal, liveUpdate }: { goal?: OperatorGoal; liveUpdate?: GoalLiveUpdate }) {
  const task = goal?.assignments.find((item) => ["running", "blocked"].includes(item.status) && item.previewTarget) ?? goal?.assignments.find((item) => item.previewTarget);
  if (task?.previewTarget) {
    const target = task.previewTarget;
    const revision = encodeURIComponent(target.revision || "current");
    const label = target.title || (target.kind === "browser" ? "Browser task" : "Workspace file");
    const source = target.kind === "browser" ? `/api/browser/previews/${encodeURIComponent(target.resource_id)}?revision=${revision}` : `/api/workspace/previews/${encodeURIComponent(target.resource_id)}?revision=${revision}`;
    return <aside aria-label={`${label} preview`} className={styles.preview}>
      {/* Authenticated task previews are dynamic backend images, not optimizable public assets. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img alt={`Preview of ${label}`} src={source} />
    </aside>;
  }
  return liveUpdate?.tool?.status === "running" ? <aside className={styles.preview}><GoalWorkPreview activity={liveUpdate.tool} /></aside> : null;
}
