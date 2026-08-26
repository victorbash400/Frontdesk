import { CalendarDays, Cloud, FileSpreadsheet, FileText, Globe2, ListChecks, Mail, Video } from "lucide-react";

import type { GoalToolActivity } from "../types/goal";
import styles from "./GoalWorkPreview.module.css";

const services = {
  browser: { Icon: Globe2, label: "Browser" },
  calendar: { Icon: CalendarDays, label: "Google Calendar" },
  docs: { Icon: FileText, label: "Google Docs" },
  drive: { Icon: Cloud, label: "Google Drive" },
  gmail: { Icon: Mail, label: "Gmail" },
  goal: { Icon: ListChecks, label: "Front Desk" },
  meet: { Icon: Video, label: "Google Meet" },
  sheets: { Icon: FileSpreadsheet, label: "Google Sheets" },
  workspace: { Icon: Cloud, label: "Google Workspace" },
};

export function GoalWorkPreview({ activity }: { activity: GoalToolActivity }) {
  const detail = services[activity.service as keyof typeof services] ?? services.workspace;
  const active = activity.status === "running";
  return <section aria-label={`${detail.label}: ${activity.message}`} aria-live="polite" className={styles.preview} data-active={active}>
    <span className={styles.icon}><detail.Icon aria-hidden="true" /></span>
    <span className={styles.copy}><small>{detail.label}</small><strong>{activity.message}</strong></span>
    <span aria-hidden="true" className={styles.shimmer} />
  </section>;
}
