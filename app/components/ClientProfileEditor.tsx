"use client";

import { Check, ChevronLeft, FileUser } from "lucide-react";
import { useState } from "react";

import type { FileSystemNode } from "../types/filesystem";
import styles from "./ClientProfileEditor.module.css";

type ClientProfileEditorProps = {
  clientName: string;
  profile: FileSystemNode;
  onBack: () => void;
  onSave: (content: string) => void;
};

export function ClientProfileEditor({ clientName, profile, onBack, onSave }: ClientProfileEditorProps) {
  const [content, setContent] = useState(profile.content ?? "");
  const [error, setError] = useState<string>();
  const changed = content !== (profile.content ?? "");

  function save() {
    try {
      onSave(content);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save the client profile.");
    }
  }

  return (
    <section className={styles.editor}>
      <header>
        <button aria-label="Back to client" onClick={onBack} title="Back to client" type="button"><ChevronLeft aria-hidden="true" /></button>
        <span><FileUser aria-hidden="true" /><strong>Client Profile</strong></span>
        <button className={styles.save} disabled={!changed} onClick={save} type="button"><Check aria-hidden="true" />Save</button>
      </header>
      <article>
        <h1>Client Profile</h1>
        <p>{clientName}</p>
        <label htmlFor="client-profile-content">Profile</label>
        <textarea aria-label="Client profile text" autoFocus id="client-profile-content" onChange={(event) => { setContent(event.target.value); setError(undefined); }} placeholder="Add the client context Front Desk should know." spellCheck="true" value={content} />
        {error ? <small role="alert">{error}</small> : null}
      </article>
    </section>
  );
}
