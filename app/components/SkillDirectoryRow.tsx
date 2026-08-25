import { Check, FileText, Plus } from "lucide-react";

import type { CatalogSkill } from "../types/skill";
import styles from "./SkillDirectoryRow.module.css";

export function SkillDirectoryRow({ added, onAdd, onOpen, skill }: { added: boolean; onAdd: () => void; onOpen: () => void; skill: CatalogSkill }) {
  return <article className={styles.row}>
    <button className={styles.open} onClick={onOpen} type="button"><FileText aria-hidden="true" /><span><strong>{skill.name}</strong><small>{skill.description}</small></span></button>
    {skill.source === "user" ? <span className={styles.added}><Check aria-hidden="true" />Added</span> : <button className={added ? styles.added : styles.add} disabled={added} onClick={onAdd} type="button">{added ? <Check aria-hidden="true" /> : <Plus aria-hidden="true" />}{added ? "Added" : "Add"}</button>}
  </article>;
}
