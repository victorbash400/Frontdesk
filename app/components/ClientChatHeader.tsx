import { PanelLeft } from "lucide-react";

import styles from "./ClientChatHeader.module.css";

type ClientChatHeaderProps = {
  onDrawerToggle: () => void;
};

export function ClientChatHeader({ onDrawerToggle }: ClientChatHeaderProps) {
  return (
    <header className={styles.header}>
      <button aria-label="Open chats" onClick={onDrawerToggle} title="Open chats" type="button"><PanelLeft aria-hidden="true" /></button>
      <strong>Agent</strong>
    </header>
  );
}
