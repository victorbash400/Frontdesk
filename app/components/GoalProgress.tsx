import { Check, LoaderCircle } from "lucide-react";

import type { GoalStatus } from "../types/goal";
import styles from "./GoalProgress.module.css";

export function GoalProgress({ status }: { status: GoalStatus }) {
  const completed = status === "completed";
  const ready = status === "ready";
  return (
    <section aria-label="Goal progress" className={styles.progress} data-completed={completed} data-ready={ready}>
      <span className={styles.state}>{completed ? <Check aria-hidden="true" /> : ready ? null : <LoaderCircle aria-hidden="true" />}<strong>{completed ? "Goal completed" : ready ? "Ready to start" : "Front Desk is working"}</strong></span>
      <span aria-hidden="true" className={styles.track}><span /></span>
      <p>{completed ? "The goal has been marked complete." : ready ? "Start this saved goal when Operator should begin working." : "Execution activity will appear here when the agent runtime is connected."}</p>
    </section>
  );
}
