import type { PluginDefinition } from "../lib/pluginDirectory";
import type { OperatorSkill } from "../types/skill";
import { GoalPluginSelector } from "./GoalPluginSelector";
import { GoalSkillSelector } from "./GoalSkillSelector";
import styles from "./GoalCapabilitySelector.module.css";

type GoalCapabilitySelectorProps = {
  plugins: PluginDefinition[];
  pluginIds: string[];
  skills: OperatorSkill[];
  skillIds: string[];
  onPluginIdsChange: (ids: string[]) => void;
  onSkillIdsChange: (ids: string[]) => void;
};

export function GoalCapabilitySelector({ plugins, pluginIds, skills, skillIds, onPluginIdsChange, onSkillIdsChange }: GoalCapabilitySelectorProps) {
  const visibleSkills = skills
    .filter((skill) => !skill.pluginId || pluginIds.includes(skill.pluginId))
    .toSorted((left, right) => (left.pluginId || "").localeCompare(right.pluginId || "") || left.name.localeCompare(right.name));

  function changePlugins(ids: string[]) {
    const availableSkillIds = new Set(skills.filter((skill) => !skill.pluginId || ids.includes(skill.pluginId)).map((skill) => skill.id));
    onPluginIdsChange(ids);
    onSkillIdsChange(skillIds.filter((id) => availableSkillIds.has(id)));
  }

  return (
    <section aria-label="Goal capabilities" className={styles.capabilities}>
      <GoalPluginSelector onChange={changePlugins} plugins={plugins} selectedIds={pluginIds} />
      <GoalSkillSelector onChange={onSkillIdsChange} plugins={plugins} selectedIds={skillIds} skills={visibleSkills} />
    </section>
  );
}
