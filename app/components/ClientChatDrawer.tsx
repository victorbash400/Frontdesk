import { PanelLeftClose, Search, SquarePen, Trash2 } from "lucide-react";

import type { ClientChat } from "./clientChatTypes";
import styles from "./ClientChatDrawer.module.css";

type ClientChatDrawerProps = {
  activeId: string;
  chats: ClientChat[];
  open: boolean;
  query: string;
  onClose: () => void;
  onDelete: (id: string) => void;
  onNewChat: () => void;
  onQueryChange: (query: string) => void;
  onSelect: (id: string) => void;
};

export function ClientChatDrawer({ activeId, chats, open, query, onClose, onDelete, onNewChat, onQueryChange, onSelect }: ClientChatDrawerProps) {
  const filtered = chats.filter((chat) => chat.title.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()));
  return (
    <aside aria-hidden={!open} className={styles.drawer} data-open={open} inert={!open ? true : undefined}>
      <header>
        <strong>Chats</strong>
        <button aria-label="Close chats" onClick={onClose} title="Close chats" type="button"><PanelLeftClose aria-hidden="true" /></button>
      </header>
      <button className={styles.primary} onClick={onNewChat} type="button"><SquarePen aria-hidden="true" /><span>New chat</span></button>
      <label className={styles.search}>
        <Search aria-hidden="true" />
        <input aria-label="Search chats" onChange={(event) => onQueryChange(event.target.value)} placeholder="Search chats" type="search" value={query} />
      </label>
      <nav aria-label="Client chats">
        {filtered.map((chat) => (
          <span className={styles.row} data-active={chat.id === activeId} key={chat.id}>
            <button onClick={() => onSelect(chat.id)} title={chat.title} type="button">{chat.title}</button>
            <button aria-label={`Delete ${chat.title}`} onClick={() => onDelete(chat.id)} title="Delete chat" type="button"><Trash2 aria-hidden="true" /></button>
          </span>
        ))}
      </nav>
    </aside>
  );
}
