import { SquareTerminal } from "lucide-react";

import type { ClientChatMessage } from "./clientChatTypes";
import styles from "./ClientToolIndicator.module.css";

type ClientToolIndicatorProps = {
  item: Extract<ClientChatMessage, { kind: "tool" }>;
};

export function ClientToolIndicator({ item }: ClientToolIndicatorProps) {
  return (
    <p className={styles.indicator} data-status={item.status}>
      <SquareTerminal aria-hidden="true" />
      <span>{item.label}</span>
    </p>
  );
}
