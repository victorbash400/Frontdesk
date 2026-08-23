"use client";

import { Check } from "lucide-react";
import { useState } from "react";

import type { OperatorSkill } from "../types/skill";
import styles from "./SkillEditor.module.css";

type SkillEditorProps = {
  skill: OperatorSkill;
  onSave: (update: Pick<OperatorSkill, "name" | "description" | "instructions">) => void;
};

export function SkillEditor({ skill, onSave }: SkillEditorProps) {
  const [name, setName] = useState(skill.name);
  const [description, setDescription] = useState(skill.description);
  const [instructions, setInstructions] = useState(skill.instructions);
  const [error, setError] = useState<string>();
  const changed = name !== skill.name || description !== skill.description || instructions !== skill.instructions;

  function save() {
    try {
      onSave({ name, description, instructions });
      setError(undefined);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save this skill.");
    }
  }

  return (
    <article className={styles.editor}>
      <input aria-label="Skill name" className={styles.name} onChange={(event) => { setName(event.target.value); setError(undefined); }} value={name} />
      <input aria-label="Skill description" className={styles.description} onChange={(event) => setDescription(event.target.value)} value={description} />
      <textarea aria-label="Skill instructions" onChange={(event) => setInstructions(event.target.value)} placeholder="Write the instructions Operator should follow." spellCheck="true" value={instructions} />
      <footer>
        {error ? <small role="alert">{error}</small> : null}
        <button disabled={!changed || !name.trim()} onClick={save} type="button"><Check aria-hidden="true" />Save</button>
      </footer>
    </article>
  );
}
