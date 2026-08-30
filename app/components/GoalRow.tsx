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
  runtimeOnline: boolean;
  selected: boolean;
  selecting: boolean;
};

export function GoalRow({ detail, expanded, goal, liveUpdate, onSelect, runtimeOnline, selected, selecting }: GoalRowProps) {
  return (
    <article className={styles.row} data-expanded={!selecting && expanded} data-running={!selecting && rowState(goal, liveUpdate, runtimeOnline) === "running"} data-selected={selected} data-selecting={selecting} data-state={rowState(goal, liveUpdate, runtimeOnline)}>
      <button aria-expanded={selecting ? undefined : expanded} aria-label={selecting ? `${selected ? "Deselect" : "Select"} ${goal.text}` : `${goal.text}, ${statusLabel(goal.status)}`} aria-pressed={selecting ? selected : undefined} onClick={onSelect} type="button">
        <span className={styles.marker}>{selecting ? selected ? <Check aria-hidden="true" /> : null : marker(goal, liveUpdate, runtimeOnline)}</span>
        <span className={styles.copy}><strong>{goal.text}</strong></span>
        {selecting ? null : <ChevronDown aria-hidden="true" className={styles.chevron} />}
      </button>
      <section aria-hidden={selecting || !expanded} className={styles.reveal} inert={selecting || !expanded ? true : undefined}><span>{detail}</span></section>
    </article>
  );
}

function marker(goal: OperatorGoal, liveUpdate: GoalLiveUpdate | undefined, runtimeOnline: boolean) {
  const state = rowState(goal, liveUpdate, runtimeOnline);
  if (state === "planning" || state === "running" || state === "queued") return <LoaderCircle aria-hidden="true" />;
  if (state === "failed") return <X aria-hidden="true" />;
  if (state === "completed") return <Check aria-hidden="true" />;
  if (state === "paused" || state === "blocked" || state === "cancelled") return <Pause aria-hidden="true" />;
  return null;
}

function rowState(goal: OperatorGoal, liveUpdate: GoalLiveUpdate | undefined, runtimeOnline: boolean) {
  if (goal.status === "completed") return "completed";
  if (!runtimeOnline && ["planning", "queued", "running"].includes(goal.runState)) return "paused";
  if (liveUpdate?.state === "planning" || liveUpdate?.state === "running") return liveUpdate.state;
  return liveUpdate?.state ?? goal.runState;
}

function statusLabel(status: OperatorGoal["status"]) {
  if (status === "active") return "Active";
  if (status === "completed") return "Completed";
  if (status === "paused") return "Paused";
  return "Active";
}
