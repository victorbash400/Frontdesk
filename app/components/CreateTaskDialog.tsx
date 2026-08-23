"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import type { FileSystemNode } from "../types/filesystem";
import styles from "./CreateTaskDialog.module.css";

type CreateTaskDialogProps = {
  clients: FileSystemNode[];
  open: boolean;
  onCancel: () => void;
  onSubmit: (clientId: string, text: string) => void;
};

export function CreateTaskDialog({ clients, open, onCancel, onSubmit }: CreateTaskDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [selectedClientId, setSelectedClientId] = useState(clients[0]?.id ?? "");
  const [text, setText] = useState("");
  const [error, setError] = useState<string>();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setSelectedClientId(clients[0]?.id ?? "");
      setText("");
      setError(undefined);
      dialog.showModal();
    } else if (!open && dialog.open) dialog.close();
  }, [clients, open]);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!selectedClientId || !text.trim()) return;
    try {
      onSubmit(selectedClientId, text.trim());
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create this task.");
    }
  }

  return (
    <dialog className={styles.dialog} onCancel={onCancel} ref={dialogRef}>
      <form onSubmit={submit}>
        <h2>New Task</h2>
        <label>Client<select aria-label="Task client" onChange={(event) => setSelectedClientId(event.target.value)} value={selectedClientId}>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}</select></label>
        <label>Task<textarea aria-label="Task instructions" autoFocus onChange={(event) => setText(event.target.value)} placeholder="What should Operator do?" rows={6} value={text} /></label>
        {error ? <p role="alert">{error}</p> : null}
        <footer><button onClick={onCancel} type="button">Cancel</button><button disabled={!selectedClientId || !text.trim()} type="submit">Create Task</button></footer>
      </form>
    </dialog>
  );
}
