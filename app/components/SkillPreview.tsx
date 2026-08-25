import { ArrowLeft, Check, ExternalLink, Plus } from "lucide-react";

import type { CatalogSkill } from "../types/skill";
import styles from "./SkillPreview.module.css";

export function SkillPreview({ added, onAdd, onBack, skill }: { added: boolean; onAdd: () => void; onBack: () => void; skill: CatalogSkill }) {
  return <section className={styles.preview}>
    <header><button aria-label="Back to skills" onClick={onBack} type="button"><ArrowLeft aria-hidden="true" /></button><span><h1>{skill.name}</h1><p>{skill.description}</p></span><button className={styles.add} disabled={added} onClick={onAdd} type="button">{added ? <Check aria-hidden="true" /> : <Plus aria-hidden="true" />}{added ? "Added" : "Add skill"}</button></header>
    <section><h2>Instructions</h2><p>{skill.instructions}</p></section>
    {skill.sourceUrl ? <a href={skill.sourceUrl} rel="noreferrer" target="_blank">View source <ExternalLink aria-hidden="true" /></a> : null}
  </section>;
}
