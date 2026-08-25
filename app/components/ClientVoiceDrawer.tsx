import { PanelLeftClose, Search, SquarePen, Trash2 } from "lucide-react";
import type { ClientVoiceSession } from "../types/voice";
import styles from "./ClientChatDrawer.module.css";

function sessionTitle(session: ClientVoiceSession) {
  return session.transcript.find((entry) => entry.role === "user" && entry.final)?.text || "New voice chat";
}

export function ClientVoiceDrawer({ activeId, onClose, onDelete, onNew, onQueryChange, onSelect, open, query, sessions }: { activeId: string; onClose: () => void; onDelete: (id: string) => void; onNew: () => void; onQueryChange: (value: string) => void; onSelect: (id: string) => void; open: boolean; query: string; sessions: ClientVoiceSession[] }) {
  const normalized = query.trim().toLocaleLowerCase();
  const filtered = sessions.filter((session) => sessionTitle(session).toLocaleLowerCase().includes(normalized));
  return <aside aria-hidden={!open} className={styles.drawer} data-open={open} inert={!open ? true : undefined}>
    <header><strong>Voice chats</strong><button aria-label="Close voice history" onClick={onClose} title="Close voice history" type="button"><PanelLeftClose aria-hidden="true" /></button></header>
    <button className={styles.primary} onClick={onNew} type="button"><SquarePen aria-hidden="true" /><span>New voice chat</span></button>
    <label className={styles.search}><Search aria-hidden="true" /><input aria-label="Search voice chats" onChange={(event) => onQueryChange(event.target.value)} placeholder="Search voice chats" type="search" value={query} /></label>
    <nav aria-label="Past voice chats">{filtered.map((session) => <span className={styles.row} data-active={session.id === activeId} key={session.id}><button onClick={() => onSelect(session.id)} title={sessionTitle(session)} type="button">{sessionTitle(session)}</button><button aria-label={`Delete ${sessionTitle(session)}`} onClick={() => onDelete(session.id)} title="Delete voice chat" type="button"><Trash2 aria-hidden="true" /></button></span>)}</nav>
  </aside>;
}
