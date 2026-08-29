import type { MailThread } from "../types/mail";
import { EmailThreadRow } from "./EmailThreadRow";
import styles from "./EmailThreadList.module.css";

export function EmailThreadList({ selectedId, threads, onSelect }: { selectedId?: string; threads: MailThread[]; onSelect: (id: string) => void }) {
  return <section aria-label="Customer email" className={styles.list}>{threads.map((thread) => <EmailThreadRow key={thread.id} onSelect={() => onSelect(thread.id)} selected={thread.id === selectedId} thread={thread} />)}</section>;
}
