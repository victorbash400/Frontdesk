import { AudioLines, PanelLeft } from "lucide-react";
import styles from "./ClientChatHeader.module.css";

export function ClientVoiceHeader({ onHistoryToggle, onVoicePickerToggle, title }: { onHistoryToggle: () => void; onVoicePickerToggle: () => void; title: string }) {
  return <header className={styles.header}>
    <button aria-label="Open voice history" onClick={onHistoryToggle} title="Open voice history" type="button"><PanelLeft aria-hidden="true" /></button>
    <strong title={title}>{title}</strong>
    <button aria-label="Choose voice" onClick={onVoicePickerToggle} title="Choose voice" type="button"><AudioLines aria-hidden="true" /></button>
  </header>;
}
