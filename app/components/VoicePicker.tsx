import { ChevronLeft, ChevronRight } from "lucide-react";
import { VoiceOrb } from "./VoiceOrb";
import styles from "./VoicePicker.module.css";

export type VoiceOption = { id: string; name: string; description: string; hue: number };

export function VoicePicker({ error, onPreview, onSelect, options, previewing, selected }: { error?: string; onPreview: () => void; onSelect: (voice: VoiceOption) => void; options: VoiceOption[]; previewing: boolean; selected: VoiceOption }) {
  const index = options.findIndex((voice) => voice.id === selected.id);
  const move = (direction: number) => onSelect(options[(index + direction + options.length) % options.length]);
  return <section aria-label="Choose voice" className={styles.picker}>
    <header>Voice</header>
    <div className={styles.carousel}><button aria-label="Previous voice" onClick={() => move(-1)} type="button"><ChevronLeft aria-hidden="true" /></button><div className={styles.orb}><VoiceOrb audioLevel={0} hue={selected.hue} mode="idle" /></div><button aria-label="Next voice" onClick={() => move(1)} type="button"><ChevronRight aria-hidden="true" /></button></div>
    <strong>{selected.name}</strong><span>{selected.description}</span>
    <button className={styles.done} disabled={previewing} onClick={onPreview} type="button">{previewing ? "Playing" : "Try this voice"}</button>
    {error ? <p role="alert">{error}</p> : null}
    <nav aria-label="Voice choices">{options.map((voice) => <button aria-label={`Choose ${voice.name}`} aria-current={voice.id === selected.id ? "true" : undefined} key={voice.id} onClick={() => onSelect(voice)} type="button" />)}</nav>
  </section>;
}
