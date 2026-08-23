"use client";

import { FormEvent, useEffect, useRef, useState } from "react";

import styles from "./CreateItemDialog.module.css";

type CreateItemDialogProps = {
  open: boolean;
  title: string;
  submitLabel: string;
  initialName?: string;
  onCancel: () => void;
  onSubmit: (name: string) => void;
};

export function CreateItemDialog({ open, title, submitLabel, initialName = "", onCancel, onSubmit }: CreateItemDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState(initialName);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setName(initialName);
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [initialName, open]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanName = name.trim();
    if (cleanName) onSubmit(cleanName);
  }

  return (
    <dialog className={styles.dialog} onCancel={onCancel} ref={dialogRef}>
      <form onSubmit={submit}>
        <h2>{title}</h2>
        <label htmlFor="item-name">Name</label>
        <input autoFocus id="item-name" onChange={(event) => setName(event.target.value)} value={name} />
        <footer>
          <button onClick={onCancel} type="button">Cancel</button>
          <button disabled={!name.trim()} type="submit">{submitLabel}</button>
        </footer>
      </form>
    </dialog>
  );
}
