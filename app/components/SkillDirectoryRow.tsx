import { FileText, Trash2 } from "lucide-react";
import type { OperatorSkill } from "../types/skill";
import styles from "./SkillDirectoryRow.module.css";

export function SkillDirectoryRow({ onDelete, onOpen, skill }: { onDelete: () => void; onOpen: () => void; skill: OperatorSkill }) {
  return <li className={styles.row}><button className={styles.open} onClick={onOpen} type="button"><FileText aria-hidden="true" /><span><strong>{skill.name}</strong><small>{skill.description}</small></span></button>{skill.deletable ? <button aria-label={`Delete ${skill.name}`} className={styles.delete} onClick={onDelete} title={`Delete ${skill.name}`} type="button"><Trash2 aria-hidden="true" /></button> : null}</li>;
}
