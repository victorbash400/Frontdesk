import { FileText } from "lucide-react";

import type { OperatorSkill } from "../types/skill";
import styles from "./GoalSkillRow.module.css";

type GoalSkillRowProps = {
  enabled: boolean;
  skill: OperatorSkill;
  onToggle: () => void;
};

export function GoalSkillRow({ enabled, skill, onToggle }: GoalSkillRowProps) {
  const action = enabled ? "Remove" : "Attach";
  return (
    <article className={styles.row}>
      <span className={styles.icon}><FileText aria-hidden="true" /></span>
      <span className={styles.copy}><strong>{skill.name}</strong><small>{skill.description || "No description"}</small></span>
      <button aria-label={`${action} ${skill.name}`} aria-checked={enabled} className={styles.switch} onClick={onToggle} role="switch" title={`${action} ${skill.name}`} type="button"><span /></button>
    </article>
  );
}
