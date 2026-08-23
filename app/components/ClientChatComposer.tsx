import { ArrowUp, Paperclip } from "lucide-react";
import { useState, type FormEvent, type KeyboardEvent } from "react";

import styles from "./ClientChatComposer.module.css";

type ClientChatComposerProps = {
  onSend: (text: string) => void;
};

export function ClientChatComposer({ onSend }: ClientChatComposerProps) {
  const [text, setText] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (!value) return;
    onSend(value);
    setText("");
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <form className={styles.composer} onSubmit={submit}>
      <textarea aria-label="Message Operator" onChange={(event) => setText(event.target.value)} onKeyDown={handleKeyDown} placeholder="Message Operator" rows={3} value={text} />
      <footer>
        <label aria-label="Attach files" title="Attach files">
          <Paperclip aria-hidden="true" />
          <input multiple type="file" />
        </label>
        <button aria-label="Send message" disabled={!text.trim()} title="Send message" type="submit"><ArrowUp aria-hidden="true" /></button>
      </footer>
    </form>
  );
}
