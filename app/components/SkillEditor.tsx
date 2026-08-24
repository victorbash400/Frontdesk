"use client";

import { Check, ChevronLeft, FileText } from "lucide-react";
import { useState } from "react";

import type { OperatorSkill } from "../types/skill";
import styles from "./SkillEditor.module.css";

type SkillEditorProps = {
  skill: OperatorSkill;
  onBack: () => void;
  onSave: (update: Pick<OperatorSkill, "name" | "description" | "instructions">) => void;
};

export function SkillEditor({ skill, onBack, onSave }: SkillEditorProps) {
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
    <section className={styles.editor}>
      <header>
        <button aria-label="Back to skills" onClick={onBack} title="Back to skills" type="button"><ChevronLeft aria-hidden="true" /></button>
        <span><FileText aria-hidden="true" /><strong>{skill.name}</strong></span>
        <button className={styles.save} disabled={!changed || !name.trim()} onClick={save} type="button"><Check aria-hidden="true" />Save</button>
      </header>
      <article>
        <input aria-label="Skill name" className={styles.name} onChange={(event) => { setName(event.target.value); setError(undefined); }} value={name} />
        <input aria-label="When to use this skill" className={styles.description} onChange={(event) => setDescription(event.target.value)} placeholder="When should Front Desk use this skill?" value={description} />
        <label htmlFor="skill-instructions">Instructions</label>
        <textarea aria-label="Skill instructions" id="skill-instructions" onChange={(event) => setInstructions(event.target.value)} placeholder="Write the instructions Front Desk should follow." spellCheck="true" value={instructions} />
        {error ? <p role="alert">{error}</p> : null}
      </article>
    </section>
  );
}
