"use client";

import { useEffect, useRef, type CSSProperties } from "react";
import type { VoiceTranscriptEntry } from "../types/voice";
import styles from "./VoiceTranscript.module.css";

export function VoiceTranscript({ entries, expanded, hue, onExpandedChange }: { entries: VoiceTranscriptEntry[]; expanded: boolean; hue: number; onExpandedChange: (value: boolean) => void }) {
  const contentRef = useRef<HTMLDivElement>(null);
  useEffect(() => { const content = contentRef.current; if (content) content.scrollTo({ top: content.scrollHeight }); }, [entries]);
  return <section aria-label="Live transcript" className={styles.transcript} data-expanded={expanded} style={{ "--transcript-hue": hue } as CSSProperties}><div className={styles.content} ref={contentRef}>{entries.map((entry) => <p data-role={entry.role} key={entry.id}>{entry.text}</p>)}</div><button aria-label={expanded ? "Collapse transcript" : "Expand transcript"} onClick={() => onExpandedChange(!expanded)} type="button"><span aria-hidden="true" /></button></section>;
}
