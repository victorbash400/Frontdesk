import { MailCheck } from "lucide-react";
import type { MailboxState } from "../types/mailbox";
import styles from "./MailboxConnectionCard.module.css";

export function MailboxConnectionCard({ mailbox, onDisconnect }: { mailbox: MailboxState; onDisconnect: () => Promise<void> }) {
  return <section className={styles.card}><MailCheck aria-hidden="true" /><span><strong>{mailbox.email}</strong><small>{mailbox.state === "failed" ? mailbox.failure : "Listening for new customer email"}</small></span><button onClick={() => void onDisconnect()} type="button">Disconnect</button></section>;
}
