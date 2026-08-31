import type { MailThread } from "../types/mail";
import { EmailThreadRow } from "./EmailThreadRow";
import styles from "./EmailThreadList.module.css";

export function EmailThreadList({ selectedId, threads, onSelect, onDelete }: { selectedId?: string; threads: MailThread[]; onSelect: (id: string) => void; onDelete: (threadId: string) => Promise<void> }) {
  return <section aria-label="Customer email" className={styles.list}>{threads.map((thread) => <EmailThreadRow key={thread.id} onDelete={onDelete} onSelect={() => onSelect(thread.id)} selected={thread.id === selectedId} thread={thread} />)}</section>;
}
