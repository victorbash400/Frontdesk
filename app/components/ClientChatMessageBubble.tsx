import type { ClientChatMessage } from "./clientChatTypes";
import { ClientToolIndicator } from "./ClientToolIndicator";
import styles from "./ClientChatMessageBubble.module.css";

type ClientChatMessageBubbleProps = {
  message: ClientChatMessage;
};

export function ClientChatMessageBubble({ message }: ClientChatMessageBubbleProps) {
  if (message.kind === "tool") return <ClientToolIndicator item={message} />;
  return <p className={styles.message} data-role={message.role}>{message.text}</p>;
}
