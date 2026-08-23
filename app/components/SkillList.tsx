import { FileText } from "lucide-react";

import type { OperatorSkill } from "../types/skill";
import styles from "./SkillList.module.css";

type SkillListProps = {
  selectedId?: string;
  skills: OperatorSkill[];
  onSelect: (id: string) => void;
};

export function SkillList({ selectedId, skills, onSelect }: SkillListProps) {
  return (
    <nav aria-label="Skills" className={styles.list}>
      {skills.map((skill) => (
        <button aria-current={skill.id === selectedId ? "page" : undefined} key={skill.id} onClick={() => onSelect(skill.id)} type="button">
          <FileText aria-hidden="true" />
          <span><strong>{skill.name}</strong><small>{skill.description}</small></span>
        </button>
      ))}
    </nav>
  );
}
