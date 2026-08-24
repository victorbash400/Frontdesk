import type { ClientChatMessage } from "./clientChatTypes";
import { ClientChatMarkdown } from "./ClientChatMarkdown";
import { ClientToolIndicator } from "./ClientToolIndicator";
import { ClientReasoningIndicator } from "./ClientReasoningIndicator";
import styles from "./ClientChatMessageBubble.module.css";

type ClientChatMessageBubbleProps = {
  message: ClientChatMessage;
};

export function ClientChatMessageBubble({ message }: ClientChatMessageBubbleProps) {
  if (message.kind === "tool") return <ClientToolIndicator item={message} />;
  if (message.kind === "reasoning") return <ClientReasoningIndicator text={message.text} />;
  if (message.role === "assistant") return <ClientChatMarkdown content={message.text} />;
  return <p className={styles.message} data-role={message.role}>{message.text}</p>;
}
