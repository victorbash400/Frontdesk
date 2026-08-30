"use client";

import { RotateCcw } from "lucide-react";
import { useState } from "react";

import styles from "./EmailAgentRetryButton.module.css";

export function EmailAgentRetryButton({ disabled, messageId, onRetry }: { disabled: boolean; messageId?: string; onRetry: (messageId: string) => Promise<void> }) {
  const [error, setError] = useState<string>();
  const [submitting, setSubmitting] = useState(false);

  async function retry() {
    if (!messageId || disabled || submitting) return;
    setSubmitting(true);
    setError(undefined);
    try {
      await onRetry(messageId);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not retry the Email Agent.");
    } finally {
      setSubmitting(false);
    }
  }

  return <span className={styles.action}>
    <button aria-label="Retry Email Agent" disabled={!messageId || disabled || submitting} onClick={() => void retry()} title="Retry Email Agent" type="button"><RotateCcw aria-hidden="true" /></button>
    {error ? <small role="alert">{error}</small> : null}
  </span>;
}
