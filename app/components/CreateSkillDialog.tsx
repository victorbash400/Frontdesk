"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import styles from "./CreateSkillDialog.module.css";

type CreateSkillDialogProps = {
  open: boolean;
  onCancel: () => void;
  onSubmit: (name: string, description: string) => void;
};

export function CreateSkillDialog({ open, onCancel, onSubmit }: CreateSkillDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string>();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setName("");
      setDescription("");
      setError(undefined);
      dialog.showModal();
    } else if (!open && dialog.open) dialog.close();
  }, [open]);

  function submit(event: FormEvent) {
    event.preventDefault();
    try {
      onSubmit(name, description);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create this skill.");
    }
  }

  return (
    <dialog className={styles.dialog} onCancel={onCancel} ref={dialogRef}>
      <form onSubmit={submit}>
        <h2>New Skill</h2>
        <label>Name<input aria-invalid={Boolean(error)} autoFocus onChange={(event) => { setName(event.target.value); setError(undefined); }} value={name} /></label>
        <label>When should Operator use it?<input onChange={(event) => setDescription(event.target.value)} value={description} /></label>
        {error ? <p role="alert">{error}</p> : null}
        <footer><button onClick={onCancel} type="button">Cancel</button><button disabled={!name.trim()} type="submit">Create Skill</button></footer>
      </form>
    </dialog>
  );
}
