"use client";

import { useState } from "react";
import type { ClientNotification } from "../hooks/useClientNotifications";
import styles from "./ClientNotificationPanel.module.css";

export function ClientNotificationPanel({ notifications, error, onAnswer }: { notifications: ClientNotification[]; error?: string; onAnswer: (id: string, answer: string) => Promise<void> }) {
  return <section aria-label="Client notifications" className={styles.panel}><header><strong>Needs you</strong><small>{notifications.filter((item) => item.status === "open").length}</small></header>{error ? <p role="alert">{error}</p> : null}{notifications.length ? <ol>{notifications.map((item) => <NotificationRow item={item} key={item.id} onAnswer={onAnswer} />)}</ol> : <p>No questions or messages</p>}</section>;
}

function NotificationRow({ item, onAnswer }: { item: ClientNotification; onAnswer: (id: string, answer: string) => Promise<void> }) {
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState<string>();
  async function submit() { try { await onAnswer(item.id, answer); setError(undefined); } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not answer."); } }
  return <li><span><strong>{item.kind === "clarification" ? "Clarification" : "Update"}</strong><time dateTime={item.createdAt}>{new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(item.createdAt))}</time></span><p>{item.message}</p>{item.kind === "clarification" && item.status === "open" ? <section><input aria-label="Clarification answer" onChange={(event) => setAnswer(event.target.value)} placeholder="Reply" value={answer} /><button disabled={!answer.trim()} onClick={() => void submit()} type="button">Send</button></section> : null}{item.answer ? <small>Answered: {item.answer}</small> : null}{error ? <small role="alert">{error}</small> : null}</li>;
}
