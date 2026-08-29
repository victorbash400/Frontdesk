import { Bell } from "lucide-react";

import styles from "./EmailAttentionButton.module.css";

export function EmailAttentionButton({ count, onClick }: { count: number; onClick: () => void }) {
  return <button aria-label={`${count} email ${count === 1 ? "needs" : "need"} attention`} className={styles.button} onClick={onClick} title="Email needing attention" type="button"><Bell aria-hidden="true" />{count ? <i /> : null}</button>;
}
