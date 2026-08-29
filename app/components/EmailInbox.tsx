import type { MailThread } from "../types/mail";
import { EmailConversation } from "./EmailConversation";
import { EmailAgentActivity } from "./EmailAgentActivity";
import { EmailEmptyState } from "./EmailEmptyState";
import { EmailThreadList } from "./EmailThreadList";
import styles from "./EmailInbox.module.css";

export function EmailInbox({ selectedId, threads, onSelect }: { selectedId?: string; threads: MailThread[]; onSelect: (id: string) => void }) {
  const selected = threads.find((thread) => thread.id === selectedId) ?? threads[0];
  return <section className={styles.inbox} data-empty={!threads.length}>{threads.length ? <><EmailThreadList onSelect={onSelect} selectedId={selected?.id} threads={threads} />{selected ? <><EmailConversation thread={selected} /><EmailAgentActivity thread={selected} /></> : null}</> : <EmailEmptyState />}</section>;
}
