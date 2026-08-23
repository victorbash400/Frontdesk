import { PanelLeft } from "lucide-react";

import styles from "./ClientChatHeader.module.css";

type ClientChatHeaderProps = {
  onDrawerToggle: () => void;
  title: string;
};

export function ClientChatHeader({ onDrawerToggle, title }: ClientChatHeaderProps) {
  return (
    <header className={styles.header}>
      <button aria-label="Open chats" onClick={onDrawerToggle} title="Open chats" type="button"><PanelLeft aria-hidden="true" /></button>
      <strong title={title}>{title}</strong>
    </header>
  );
}
