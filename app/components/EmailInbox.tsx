import type { MailThread } from "../types/mail";
import { EmailConversation } from "./EmailConversation";
import { EmailAgentActivity } from "./EmailAgentActivity";
import { EmailEmptyState } from "./EmailEmptyState";
import { EmailThreadList } from "./EmailThreadList";
import styles from "./EmailInbox.module.css";

export function EmailInbox({ selectedId, threads, onSelect, onRetry, onDelete }: { selectedId?: string; threads: MailThread[]; onSelect: (id: string) => void; onRetry: (messageId: string) => Promise<void>; onDelete: (threadId: string) => Promise<void> }) {
  const selected = threads.find((thread) => thread.id === selectedId) ?? threads[0];
  return <section className={styles.inbox} data-empty={!threads.length}>{threads.length ? <><EmailThreadList onDelete={onDelete} onSelect={onSelect} selectedId={selected?.id} threads={threads} />{selected ? <><EmailConversation thread={selected} /><EmailAgentActivity onRetry={onRetry} thread={selected} /></> : null}</> : <EmailEmptyState />}</section>;
}
