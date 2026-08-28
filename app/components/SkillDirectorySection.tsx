import type { OperatorSkill } from "../types/skill";
import type { PluginDefinition } from "../lib/pluginDirectory";
import { SkillBatchIcon } from "./SkillBatchIcon";
import { SkillDirectoryRow } from "./SkillDirectoryRow";
import styles from "./SkillDirectorySection.module.css";

export function SkillDirectorySection({ onDelete, onOpen, plugin, skills, title }: { onDelete: (id: string) => void; onOpen: (id: string) => void; plugin?: PluginDefinition; skills: OperatorSkill[]; title: string }) {
  const description = plugin ? `Organization workflows that use ${plugin.name}` : title === "AquaLabs" ? "Customer support procedures for AquaLabs" : title === "Created by you" ? "Skills created and managed by your organization" : "Reusable organization procedures";
  return <section className={styles.section}><header><SkillBatchIcon plugin={plugin} title={title} /><span><h2>{title}</h2><p>{description}</p></span></header><ul>{skills.map((skill) => <SkillDirectoryRow key={skill.id} onDelete={() => onDelete(skill.id)} onOpen={() => onOpen(skill.id)} skill={skill} />)}</ul></section>;
}
