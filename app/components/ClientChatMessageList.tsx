import type { ClientChatMessage } from "./clientChatTypes";
import { ClientChatMessageBubble } from "./ClientChatMessageBubble";
import styles from "./ClientChatMessageList.module.css";

type ClientChatMessageListProps = {
  messages: ClientChatMessage[];
};

export function ClientChatMessageList({ messages }: ClientChatMessageListProps) {
  return (
    <section aria-live="polite" className={styles.messages}>
      {messages.map((message) => <ClientChatMessageBubble key={message.id} message={message} />)}
    </section>
  );
}
