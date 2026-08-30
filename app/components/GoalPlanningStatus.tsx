import styles from "./GoalPlanningStatus.module.css";

export function GoalPlanningStatus({ currentStep }: { currentStep: string }) {
  return <p className={styles.status}><span>{currentStep}</span></p>;
}
