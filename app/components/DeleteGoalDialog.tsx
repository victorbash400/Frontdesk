"use client";

import { useEffect, useRef, useState } from "react";

import styles from "./DeleteGoalDialog.module.css";

type DeleteGoalDialogProps = { goal: string; open: boolean; onCancel: () => void; onConfirm: () => Promise<void> };

export function DeleteGoalDialog({ goal, open, onCancel, onConfirm }: DeleteGoalDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) { setError(undefined); dialog.showModal(); }
    if (!open && dialog.open) dialog.close();
  }, [open]);

  async function remove() {
    try {
      setDeleting(true);
      await onConfirm();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete this goal.");
      setDeleting(false);
    }
  }

  return <dialog className={styles.dialog} onCancel={onCancel} ref={dialogRef}><section><h2>Delete goal?</h2><p>{goal}</p>{error ? <small role="alert">{error}</small> : null}<footer><button disabled={deleting} onClick={onCancel} type="button">Cancel</button><button className={styles.delete} disabled={deleting} onClick={() => void remove()} type="button">{deleting ? "Deleting…" : "Delete"}</button></footer></section></dialog>;
}
