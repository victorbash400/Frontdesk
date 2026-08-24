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
  return (
    <section aria-label="Goal capabilities" className={styles.capabilities}>
      <GoalSkillSelector onChange={onSkillIdsChange} selectedIds={skillIds} skills={skills} />
      <GoalPluginSelector onChange={onPluginIdsChange} plugins={plugins} selectedIds={pluginIds} />
    </section>
  );
}
