import type { MailMessage } from "../types/mail";
import styles from "./EmailMessageBubble.module.css";

export function EmailMessageBubble({ message }: { message: MailMessage }) {
  const outbound = message.direction === "outbound";
  return <article className={styles.message} data-direction={message.direction}><header><strong>{outbound ? "Front Desk" : senderLabel(message.sender)}</strong><time dateTime={message.sentAt}>{formatDate(message.sentAt)}</time></header><p>{message.body}</p></article>;
}

function senderLabel(value: string) { return value.match(/^\s*([^<]+)\s*</)?.[1]?.trim() || value; }
function formatDate(value: string) { return new Intl.DateTimeFormat(undefined, { day: "numeric", hour: "numeric", minute: "2-digit", month: "short" }).format(new Date(value)); }
