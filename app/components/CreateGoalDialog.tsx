"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import type { FileSystemNode } from "../types/filesystem";
import type { OperatorSkill } from "../types/skill";
import { GoalCapabilitySelector } from "./GoalCapabilitySelector";
import styles from "./CreateGoalDialog.module.css";

type CreateGoalDialogProps = {
  clients: FileSystemNode[];
  plugins: PluginDefinition[];
  skills: OperatorSkill[];
  open: boolean;
  onCancel: () => void;
  onSubmit: (clientId: string, text: string, skillIds: string[], pluginIds: string[]) => Promise<void>;
};

export function CreateGoalDialog({ clients, open, plugins, skills, onCancel, onSubmit }: CreateGoalDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [selectedClientId, setSelectedClientId] = useState(clients[0]?.id ?? "");
  const [text, setText] = useState("");
  const [skillIds, setSkillIds] = useState<string[]>([]);
  const [pluginIds, setPluginIds] = useState<string[]>([]);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      setSelectedClientId(clients[0]?.id ?? "");
      setText("");
      setSkillIds([]);
      setPluginIds([]);
      setError(undefined);
      dialog.showModal();
    } else if (!open && dialog.open) dialog.close();
  }, [clients, open]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selectedClientId || !text.trim()) return;
    try {
      await onSubmit(selectedClientId, text.trim(), skillIds, pluginIds);
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create this goal.");
    }
  }

  return (
    <dialog className={styles.dialog} onCancel={onCancel} ref={dialogRef}>
      <form onSubmit={submit}>
        <h2>New Goal</h2>
        <section className={styles.body}>
          <label className={styles.field}>Client<select aria-label="Goal client" onChange={(event) => setSelectedClientId(event.target.value)} value={selectedClientId}>{clients.map((client) => <option key={client.id} value={client.id}>{client.name}</option>)}</select></label>
          <label className={styles.field}>Goal<textarea aria-label="Goal instructions" autoFocus onChange={(event) => setText(event.target.value)} placeholder="What should Front Desk accomplish?" rows={6} value={text} /></label>
          <GoalCapabilitySelector onPluginIdsChange={setPluginIds} onSkillIdsChange={setSkillIds} pluginIds={pluginIds} plugins={plugins} skillIds={skillIds} skills={skills} />
          {error ? <p role="alert">{error}</p> : null}
        </section>
        <footer><button onClick={onCancel} type="button">Cancel</button><button disabled={!selectedClientId || !text.trim()} type="submit">Create and Start</button></footer>
      </form>
    </dialog>
  );
}
