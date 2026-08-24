import { Brain } from "lucide-react";

import styles from "./ClientReasoningIndicator.module.css";

export function ClientReasoningIndicator({ text }: { text: string }) {
  return (
    <details className={styles.reasoning}>
      <summary><Brain aria-hidden="true" size={14} /><span>Reasoning</span></summary>
      <p>{text}</p>
    </details>
  );
}
