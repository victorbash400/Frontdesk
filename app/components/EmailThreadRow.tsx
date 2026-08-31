"use client";

import { Trash2 } from "lucide-react";
import { useState } from "react";

import type { MailThread } from "../types/mail";
import styles from "./EmailThreadRow.module.css";

export function EmailThreadRow({ selected, thread, onSelect, onDelete }: { selected: boolean; thread: MailThread; onSelect: () => void; onDelete: (threadId: string) => Promise<void> }) {
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string>();

  async function remove() {
    if (deleting) return;
    setDeleting(true);
    setError(undefined);
    try {
      await onDelete(thread.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete the conversation.");
      setDeleting(false);
    }
  }

  return <div className={styles.item} data-deleting={deleting}>
    <button aria-current={selected ? "true" : undefined} className={styles.row} onClick={onSelect} type="button"><span><strong>{thread.clientName}</strong><time dateTime={thread.updatedAt}>{formatTime(thread.updatedAt)}</time></span><b>{thread.subject || "No subject"}</b><p>{singleLine(thread.preview)}</p><small data-attention={thread.attentionRequired}>{thread.attentionRequired ? "Needs attention" : statusLabel(thread)}</small></button>
    <button aria-label={`Delete conversation with ${thread.clientName}`} className={styles.delete} disabled={deleting} onClick={() => void remove()} title="Delete conversation" type="button"><Trash2 aria-hidden="true" /></button>
    {error ? <small className={styles.error} role="alert">{error}</small> : null}
  </div>;
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
