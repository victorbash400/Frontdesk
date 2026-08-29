import { Mail } from "lucide-react";

import styles from "./EmailEmptyState.module.css";

export function EmailEmptyState() {
  return <section className={styles.empty}><Mail aria-hidden="true" /><strong>No customer emails yet</strong><p>New messages will appear here while the Email Agent files and reviews them.</p></section>;
}
