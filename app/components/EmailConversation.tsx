import type { MailThread } from "../types/mail";
import { EmailMessageBubble } from "./EmailMessageBubble";
import styles from "./EmailConversation.module.css";

export function EmailConversation({ thread }: { thread: MailThread }) {
  return <section className={styles.conversation}><header><strong>{thread.subject || "No subject"}</strong><small>{thread.clientName} · {thread.customerEmail}</small></header><section>{thread.messages.map((message) => <EmailMessageBubble key={message.id} message={message} />)}</section></section>;
}
