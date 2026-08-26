"use client";

import { Check, ChevronLeft, FileText } from "lucide-react";
import { useState } from "react";

import type { FileSystemNode } from "../types/filesystem";
import styles from "./MarkdownDocumentEditor.module.css";

type MarkdownDocumentEditorProps = {
  document: FileSystemNode;
  onBack: () => void;
  onSave: (content: string) => void;
};

export function MarkdownDocumentEditor({ document, onBack, onSave }: MarkdownDocumentEditorProps) {
  const [content, setContent] = useState(document.content ?? "");
  const [error, setError] = useState<string>();
  const changed = content !== (document.content ?? "");

  function save() {
    try {
      onSave(content);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save the document.");
    }
  }

  return (
    <section className={styles.editor}>
      <header>
        <button aria-label="Back to files" onClick={onBack} title="Back to files" type="button"><ChevronLeft aria-hidden="true" /></button>
        <span><FileText aria-hidden="true" /><strong>{document.name}</strong></span>
        <button className={styles.save} disabled={!changed} onClick={save} type="button"><Check aria-hidden="true" />Save</button>
      </header>
      <article>
        <h1>{document.name.replace(/\.md$/i, "")}</h1>
        <p>Markdown document</p>
        <label htmlFor={`document-${document.id}`}>Document</label>
        <textarea aria-label={`${document.name} contents`} autoFocus id={`document-${document.id}`} onChange={(event) => { setContent(event.target.value); setError(undefined); }} spellCheck="true" value={content} />
        {error ? <small role="alert">{error}</small> : null}
      </article>
    </section>
  );
}
