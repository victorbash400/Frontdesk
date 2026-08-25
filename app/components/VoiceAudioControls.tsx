"use client";

import { Mic, MicOff, Volume2, VolumeOff } from "lucide-react";
import styles from "./VoiceAudioControls.module.css";

export function VoiceAudioControls({ microphoneMuted, onMicrophoneMutedChange, onSpeakerMutedChange, onVolumeChange, speakerMuted, volume }: { microphoneMuted: boolean; onMicrophoneMutedChange: (value: boolean) => void; onSpeakerMutedChange: (value: boolean) => void; onVolumeChange: (value: number) => void; speakerMuted: boolean; volume: number }) {
  return <section aria-label="Audio controls" className={styles.controls}>
    <button aria-label={microphoneMuted ? "Unmute microphone" : "Mute microphone"} aria-pressed={microphoneMuted} onClick={() => onMicrophoneMutedChange(!microphoneMuted)} type="button">{microphoneMuted ? <MicOff aria-hidden="true" /> : <Mic aria-hidden="true" />}</button>
    <button aria-label={speakerMuted ? "Unmute speaker" : "Mute speaker"} aria-pressed={speakerMuted} onClick={() => onSpeakerMutedChange(!speakerMuted)} type="button">{speakerMuted ? <VolumeOff aria-hidden="true" /> : <Volume2 aria-hidden="true" />}</button>
    <input aria-label="Speaker volume" max="100" min="0" onChange={(event) => { const next = Number(event.target.value); onVolumeChange(next); onSpeakerMutedChange(next === 0); }} type="range" value={speakerMuted ? 0 : volume} />
  </section>;
}
