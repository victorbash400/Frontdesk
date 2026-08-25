import type { CatalogSkill, OperatorSkill } from "../types/skill";
import type { PluginDefinition } from "../lib/pluginDirectory";
import { PluginIcon } from "./PluginIcon";
import { SkillDirectoryRow } from "./SkillDirectoryRow";
import styles from "./SkillDirectorySection.module.css";

type Props = {
  addedIds: Map<string, OperatorSkill>;
  onAdd: (skill: CatalogSkill) => string;
  onOpen: (id: string) => void;
  onPreview: (skill: CatalogSkill) => void;
  plugin?: PluginDefinition;
  skills: CatalogSkill[];
  title: string;
};

export function SkillDirectorySection({ addedIds, onAdd, onOpen, onPreview, plugin, skills, title }: Props) {
  return <section className={styles.section}>
    <header>{plugin ? <PluginIcon plugin={plugin} /> : null}<span><h2>{title}</h2><p>{plugin ? `Workflows that use the ${plugin.name} plugin` : title === "Created by you" ? "Skills written and managed in Front Desk" : "Useful across clients and plugins"}</p></span></header>
    <div className={styles.rows}>{skills.map((skill) => <SkillDirectoryRow added={addedIds.has(skill.id)} key={skill.id} onAdd={() => onAdd(skill)} onOpen={() => addedIds.has(skill.id) ? onOpen(skill.id) : onPreview(skill)} skill={skill} />)}</div>
  </section>;
}
