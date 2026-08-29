import type { MailThread } from "../types/mail";
import styles from "./EmailThreadRow.module.css";

export function EmailThreadRow({ selected, thread, onSelect }: { selected: boolean; thread: MailThread; onSelect: () => void }) {
  return <button aria-current={selected ? "true" : undefined} className={styles.row} onClick={onSelect} type="button"><span><strong>{thread.clientName}</strong><time dateTime={thread.updatedAt}>{formatTime(thread.updatedAt)}</time></span><b>{thread.subject || "No subject"}</b><p>{singleLine(thread.preview)}</p><small data-attention={thread.attentionRequired}>{thread.attentionRequired ? "Needs attention" : statusLabel(thread)}</small></button>;
}

function singleLine(value: string) { return value.replace(/\s+/g, " ").trim(); }
function statusLabel(thread: MailThread) {
  if (thread.agentStatus === "processing" || thread.agentStatus === "queued") return thread.agentStatus === "queued" ? "Queued for Email Agent" : "Email Agent working";
  if (thread.agentAction === "create_goal") return "Started new work";
  if (thread.agentAction === "resume_goal") return "Continued active work";
  return `${thread.messages.length} ${thread.messages.length === 1 ? "message" : "messages"}`;
}
function formatTime(value: string) {
  const date = new Date(value);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit" }).format(date);
  return new Intl.DateTimeFormat(undefined, { day: "numeric", month: "short" }).format(date);
}
