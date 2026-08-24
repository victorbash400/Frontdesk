import type { OperatorSkill } from "../types/skill";
import { GoalSkillRow } from "./GoalSkillRow";
import styles from "./GoalSkillSelector.module.css";

type GoalSkillSelectorProps = {
  skills: OperatorSkill[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
};

export function GoalSkillSelector({ skills, selectedIds, onChange }: GoalSkillSelectorProps) {
  return (
    <section aria-label="Goal skills" className={styles.selector}>
      <header><strong>Skills</strong><small>How Operator should approach this goal</small></header>
      <section className={styles.options}>
        {skills.map((skill) => <GoalSkillRow enabled={selectedIds.includes(skill.id)} key={skill.id} onToggle={() => onChange(toggleId(selectedIds, skill.id))} skill={skill} />)}
        {!skills.length ? <p>No skills available</p> : null}
      </section>
    </section>
  );
}

function toggleId(ids: string[], id: string) {
  return ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id];
}
