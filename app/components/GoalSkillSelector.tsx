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
  const general = skills.filter((skill) => !skill.pluginId);
  const pluginGroups = plugins
    .map((plugin) => ({ plugin, skills: skills.filter((skill) => skill.pluginId === plugin.id) }))
    .filter((group) => group.skills.length);

  return (
    <section aria-label="Goal skills" className={styles.selector}>
      <header><strong>Skills</strong><small>Workflows available through the selected plugins</small></header>
      {!skills.length ? <p className={styles.empty}>Select a plugin to see its skills</p> : null}
      {general.length ? <SkillRows onChange={onChange} selectedIds={selectedIds} skills={general} title="General" /> : null}
      {pluginGroups.map(({ plugin, skills: pluginSkills }) => <SkillRows icon={<PluginIcon plugin={plugin} />} key={plugin.id} onChange={onChange} selectedIds={selectedIds} skills={pluginSkills} title={plugin.name} />)}
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
