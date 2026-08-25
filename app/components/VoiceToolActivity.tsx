import type { VoiceToolActivity as Activity } from "../types/voice";
import styles from "./VoiceToolActivity.module.css";

export function VoiceToolActivity({ activities }: { activities: Activity[] }) {
  const activity = activities.at(-1); if (!activity) return null;
  return <div aria-live="polite" className={styles.activity} data-status={activity.status}>{activity.status === "error" ? activity.error : activity.name.replaceAll("_", " ")}</div>;
}
