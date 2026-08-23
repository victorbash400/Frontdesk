import { SquareTerminal } from "lucide-react";

import type { ClientChatMessage } from "./clientChatTypes";
import styles from "./ClientToolIndicator.module.css";

type ClientToolIndicatorProps = {
  item: Extract<ClientChatMessage, { kind: "tool" }>;
};

export function ClientToolIndicator({ item }: ClientToolIndicatorProps) {
  return <span className={styles.tool} data-status={item.status}><SquareTerminal aria-hidden="true" size={14} /><strong>{item.name.replaceAll("_", " ")}</strong></span>;
}
