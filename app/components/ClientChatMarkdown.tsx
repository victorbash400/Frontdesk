import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

import styles from "./ClientChatMarkdown.module.css";


export function ClientChatMarkdown({ content }: { content: string }) {
  return <div className={styles.markdown}><Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown></div>;
}
