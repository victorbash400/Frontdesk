"use client";

import type { VoiceStatus } from "../hooks/useVoiceSession";
import styles from "./VoiceSessionButton.module.css";

export function VoiceSessionButton({ hue, onStart, onStop, status }: { hue: number; onStart: () => void; onStop: () => void; status: VoiceStatus }) {
  const active = status === "connecting" || status === "listening" || status === "speaking";
  return <button aria-label={active ? "Stop voice session" : "Start voice session"} className={styles.button} data-active={active} disabled={status === "connecting"} onClick={active ? onStop : onStart} type="button">{active ? <img alt="" aria-hidden="true" src="/stop-sherpa.svg" /> : <span aria-hidden="true" className={styles.start} style={{ color: `hsl(${(hue + 258) % 360} 62% 51%)` }} />}</button>;
}
