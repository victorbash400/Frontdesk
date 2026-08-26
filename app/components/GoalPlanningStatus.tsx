import { LoaderCircle } from "lucide-react";

import styles from "./GoalPlanningStatus.module.css";

export function GoalPlanningStatus({ currentStep }: { currentStep: string }) {
  return <p className={styles.status}><LoaderCircle aria-hidden="true" /><span>{currentStep}</span></p>;
}
