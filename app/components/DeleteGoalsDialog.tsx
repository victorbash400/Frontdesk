"use client";

import { useEffect, useRef, useState } from "react";

import styles from "./DeleteGoalsDialog.module.css";

type DeleteGoalsDialogProps = {
  count: number;
  open: boolean;
  onCancel: () => void;
  onConfirm: () => Promise<void>;
};

export function DeleteGoalsDialog({ count, open, onCancel, onConfirm }: DeleteGoalsDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  function cancel() {
    setError(undefined);
    onCancel();
  }

  async function remove() {
    setDeleting(true);
    setError(undefined);
    try {
      await onConfirm();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete the selected goals.");
    } finally {
      setDeleting(false);
    }
  }

  return <dialog className={styles.dialog} onCancel={cancel} ref={dialogRef}><section><h2>Delete {count} {count === 1 ? "goal" : "goals"}?</h2><p>This cannot be undone.</p>{error ? <small role="alert">{error}</small> : null}<footer><button disabled={deleting} onClick={cancel} type="button">Cancel</button><button className={styles.delete} disabled={deleting} onClick={() => void remove()} type="button">{deleting ? "Deleting…" : "Delete goals"}</button></footer></section></dialog>;
}
