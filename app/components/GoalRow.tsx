import { Check, ChevronDown, LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import type { OperatorGoal } from "../types/goal";
import styles from "./GoalRow.module.css";

type GoalRowProps = {
  clientName: string;
  detail: ReactNode;
  expanded: boolean;
  goal: OperatorGoal;
  onSelect: () => void;
};

export function GoalRow({ clientName, detail, expanded, goal, onSelect }: GoalRowProps) {
  return (
    <article className={styles.row} data-expanded={expanded} data-status={goal.status}>
      <button aria-expanded={expanded} aria-label={`${goal.text}, ${statusLabel(goal.status)}`} onClick={onSelect} type="button">
        <span className={styles.marker}>{goal.status === "completed" ? <Check aria-hidden="true" /> : goal.status === "active" ? <LoaderCircle aria-hidden="true" /> : null}</span>
        <span className={styles.copy}><strong>{goal.text}</strong><small>{clientName} · {statusLabel(goal.status)} · {capabilityLabel(goal.skillIds.length + goal.pluginIds.length)}</small></span>
        <ChevronDown aria-hidden="true" className={styles.chevron} />
      </button>
      <section aria-hidden={!expanded} className={styles.reveal} inert={!expanded ? true : undefined}><span>{detail}</span></section>
    </article>
  );
}

function statusLabel(status: OperatorGoal["status"]) {
  if (status === "active") return "Active";
  if (status === "completed") return "Completed";
  return "Ready";
}

function capabilityLabel(count: number) {
  return `${count} ${count === 1 ? "capability" : "capabilities"}`;
}
