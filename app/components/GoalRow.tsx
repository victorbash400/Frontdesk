import { Check, ChevronDown, LoaderCircle, Pause, X } from "lucide-react";
import type { ReactNode } from "react";

import type { GoalLiveUpdate, OperatorGoal } from "../types/goal";
import styles from "./GoalRow.module.css";

type GoalRowProps = {
  detail: ReactNode;
  expanded: boolean;
  goal: OperatorGoal;
  liveUpdate?: GoalLiveUpdate;
  onSelect: () => void;
};

export function GoalRow({ detail, expanded, goal, liveUpdate, onSelect }: GoalRowProps) {
  return (
    <article className={styles.row} data-expanded={expanded} data-running={rowState(goal, liveUpdate) === "running"} data-state={rowState(goal, liveUpdate)}>
      <button aria-expanded={expanded} aria-label={`${goal.text}, ${statusLabel(goal.status)}`} onClick={onSelect} type="button">
        <span className={styles.marker}>{marker(goal, liveUpdate)}</span>
        <span className={styles.copy}><strong>{goal.text}</strong></span>
        <ChevronDown aria-hidden="true" className={styles.chevron} />
      </button>
      <section aria-hidden={!expanded} className={styles.reveal} inert={!expanded ? true : undefined}><span>{detail}</span></section>
    </article>
  );
}

function marker(goal: OperatorGoal, liveUpdate?: GoalLiveUpdate) {
  const state = rowState(goal, liveUpdate);
  if (state === "running" || state === "queued") return <LoaderCircle aria-hidden="true" />;
  if (state === "failed") return <X aria-hidden="true" />;
  if (state === "completed") return <Check aria-hidden="true" />;
  if (state === "paused" || state === "blocked" || state === "cancelled") return <Pause aria-hidden="true" />;
  return null;
}

function rowState(goal: OperatorGoal, liveUpdate?: GoalLiveUpdate) {
  if (liveUpdate?.state === "running") return "running";
  return liveUpdate?.state ?? goal.runState;
}

function statusLabel(status: OperatorGoal["status"]) {
  if (status === "active") return "Active";
  if (status === "completed") return "Completed";
  if (status === "paused") return "Paused";
  return "Active";
}
