import { FileText } from "lucide-react";

import type { OperatorSkill } from "../types/skill";
import styles from "./SkillList.module.css";

type SkillListProps = {
  skills: OperatorSkill[];
  onOpen: (id: string) => void;
};

export function SkillList({ skills, onOpen }: SkillListProps) {
  return (
    <section aria-label="Skill files" className={styles.list}>
      <header><span>Name</span><span>When to use</span><span>Modified</span></header>
      {skills.map((skill) => (
        <button key={skill.id} onClick={() => onOpen(skill.id)} type="button">
          <span className={styles.name}><FileText aria-hidden="true" /><strong>{skill.name}</strong></span>
          <span className={styles.description}>{skill.description || "No description"}</span>
          <time dateTime={skill.updatedAt}>{formatDate(skill.updatedAt)}</time>
        </button>
      ))}
      {!skills.length ? <p>No skills match this search.</p> : null}
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(value));
}
