import { ArrowLeft, ExternalLink } from "lucide-react";
import type { OperatorSkill } from "../types/skill";
import styles from "./SkillPreview.module.css";

export function SkillPreview({ onBack, skill }: { onBack: () => void; skill: OperatorSkill }) {
  return <section className={styles.preview}><header><button aria-label="Back to skills" onClick={onBack} type="button"><ArrowLeft aria-hidden="true" /></button><span><h1>{skill.name}</h1><p>{skill.description}</p></span></header><section><h2>Instructions</h2><p>{skill.instructions}</p></section>{skill.sourceUrl ? <a href={skill.sourceUrl} rel="noreferrer" target="_blank">View source <ExternalLink aria-hidden="true" /></a> : null}</section>;
}
