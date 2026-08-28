import type { ReactNode } from "react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import type { OperatorSkill } from "../types/skill";
import { PluginIcon } from "./PluginIcon";
import { GoalSkillRow } from "./GoalSkillRow";
import styles from "./GoalSkillSelector.module.css";

type GoalSkillSelectorProps = {
  skills: OperatorSkill[];
  plugins: PluginDefinition[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
};

export function GoalSkillSelector({ skills, plugins, selectedIds, onChange }: GoalSkillSelectorProps) {
  const batches = [...new Set(skills.map((skill) => skill.batchName))];

  return (
    <section aria-label="Goal skills" className={styles.selector}>
      <header><strong>Skills</strong><small>Workflows available through the selected plugins</small></header>
      {!skills.length ? <p className={styles.empty}>Select a plugin to see its skills</p> : null}
      {batches.map((batchName) => {
        const batchSkills = skills.filter((skill) => skill.batchName === batchName);
        const pluginId = batchSkills.find((skill) => skill.pluginId)?.pluginId;
        const plugin = plugins.find((item) => item.id === pluginId);
        return <SkillRows icon={plugin ? <PluginIcon plugin={plugin} /> : undefined} key={batchName} onChange={onChange} selectedIds={selectedIds} skills={batchSkills} title={batchName} />;
      })}
    </section>
  );
}

function SkillRows({ icon, onChange, selectedIds, skills, title }: { icon?: ReactNode; onChange: (ids: string[]) => void; selectedIds: string[]; skills: OperatorSkill[]; title: string }) {
  return <section className={styles.group}>
    <header>{icon}<strong>{title}</strong></header>
    <div className={styles.options}>{skills.map((skill) => <GoalSkillRow enabled={selectedIds.includes(skill.id)} key={skill.id} onToggle={() => onChange(toggleId(selectedIds, skill.id))} skill={skill} />)}</div>
  </section>;
}

function toggleId(ids: string[], id: string) {
  return ids.includes(id) ? ids.filter((value) => value !== id) : [...ids, id];
}
