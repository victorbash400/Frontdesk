"use client";

import { useEffect, useMemo, useState } from "react";
import { useVoiceSession } from "../hooks/useVoiceSession";
import { useVoicePreview } from "../hooks/useVoicePreview";
import { loadClientVoiceSessions, saveClientVoiceSessions } from "../lib/clientVoiceStorage";
import type { ClientVoiceSession, VoiceTranscriptEntry } from "../types/voice";
import { VoiceAudioControls } from "./VoiceAudioControls";
import { ClientVoiceDrawer } from "./ClientVoiceDrawer";
import { ClientVoiceHeader } from "./ClientVoiceHeader";
import { VoiceOrb, type VoiceOrbMode } from "./VoiceOrb";
import { VoicePicker, type VoiceOption } from "./VoicePicker";
import { VoiceSessionButton } from "./VoiceSessionButton";
import { VoiceToolActivity } from "./VoiceToolActivity";
import { VoiceTranscript } from "./VoiceTranscript";
import styles from "./ClientVoicePanel.module.css";

const voices: VoiceOption[] = [
  { id: "Kore", name: "Kore", description: "Firm", hue: 0 }, { id: "Aoede", name: "Aoede", description: "Breezy", hue: 38 },
  { id: "Leda", name: "Leda", description: "Youthful", hue: 75 }, { id: "Zephyr", name: "Zephyr", description: "Bright", hue: 128 },
  { id: "Puck", name: "Puck", description: "Upbeat", hue: 178 }, { id: "Charon", name: "Charon", description: "Informative", hue: 220 },
  { id: "Fenrir", name: "Fenrir", description: "Excitable", hue: 262 }, { id: "Orus", name: "Orus", description: "Firm", hue: 304 },
  { id: "Sulafat", name: "Sulafat", description: "Warm", hue: 338 },
];

function newSession(): ClientVoiceSession { const now = Date.now(); return { id: crypto.randomUUID(), createdAt: now, updatedAt: now, transcript: [] }; }

export function ClientVoicePanel({ accountId, clientId, open }: { accountId: string; clientId: string; open: boolean }) {
  const [sessions, setSessions] = useState<ClientVoiceSession[]>([]);
  const [activeId, setActiveId] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [microphoneMuted, setMicrophoneMuted] = useState(false);
  const [speakerMuted, setSpeakerMuted] = useState(false);
  const [volume, setVolume] = useState(75);
  const [voiceName, setVoiceName] = useState("Kore");
  const active = sessions.find((session) => session.id === activeId) ?? sessions[0];
  const selectedVoice = voices.find((voice) => voice.id === voiceName) ?? voices[0];

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const saved = loadClientVoiceSessions(accountId, clientId);
      const next = saved.length ? saved : [newSession()];
      setSessions(next); setActiveId(next[0].id);
      setVoiceName(window.localStorage.getItem(`front-desk:voice-choice:${accountId}`) || "Kore");
      setLoaded(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [accountId, clientId]);
  useEffect(() => { if (loaded) saveClientVoiceSessions(accountId, clientId, sessions); }, [accountId, clientId, loaded, sessions]);

  function applyTranscript(entry: VoiceTranscriptEntry) {
    setSessions((current) => current.map((session) => session.id !== activeId ? session : { ...session, updatedAt: Date.now(), transcript: [...session.transcript.filter((item) => item.id !== entry.id), entry].sort((a, b) => a.sequence - b.sequence) }));
  }
  const voice = useVoiceSession({ clientId, microphoneMuted, onTranscript: applyTranscript, sessionId: active?.id || "unavailable", speakerMuted, volume, voiceName });
  const preview = useVoicePreview(clientId, active?.id || "unavailable");
  const stopVoice = voice.stop;
  useEffect(() => { if (!open) stopVoice(); }, [open, stopVoice]);
  const mode = useMemo<VoiceOrbMode>(() => voice.status === "speaking" ? "speaking" : voice.status === "listening" ? "listening" : "idle", [voice.status]);
  const title = active?.transcript.find((entry) => entry.role === "user" && entry.final)?.text || "Voice";

  function createSession() {
    voice.stop();
    const session = newSession();
    setSessions((current) => [session, ...current]);
    setActiveId(session.id); setDrawerOpen(false); setExpanded(false);
  }

  function deleteSession(id: string) {
    voice.stop();
    const remaining = sessions.filter((session) => session.id !== id);
    if (remaining.length) { setSessions(remaining); if (id === activeId) setActiveId(remaining[0].id); }
    else { const replacement = newSession(); setSessions([replacement]); setActiveId(replacement.id); }
  }

  function selectVoice(option: VoiceOption) {
    setVoiceName(option.id);
    window.localStorage.setItem(`front-desk:voice-choice:${accountId}`, option.id);
  }
  if (!loaded || !active) return null;

  return <aside aria-hidden={!open} aria-label="Client voice" className={styles.panel} data-open={open} inert={!open ? true : undefined}>
    <ClientVoiceHeader onHistoryToggle={() => setDrawerOpen((current) => !current)} onVoicePickerToggle={() => { voice.stop(); preview.stop(); setPickerOpen((current) => !current); }} title={pickerOpen ? "Choose voice" : title} />
    <section className={styles.body}>{pickerOpen ? <VoicePicker error={preview.error} onPreview={() => void preview.preview(selectedVoice.id)} onSelect={(option) => { preview.stop(); selectVoice(option); }} options={voices} previewing={preview.previewing} selected={selectedVoice} /> : <>
    {active.transcript.length ? <VoiceTranscript entries={active.transcript} expanded={expanded} hue={selectedVoice.hue} onExpandedChange={setExpanded} /> : null}
    <section aria-label="Front Desk voice" className={styles.stage} data-transcript-expanded={expanded && active.transcript.length > 0}>
      <VoiceOrb audioLevel={voice.audioLevel} hue={selectedVoice.hue} mode={mode} />
      <VoiceSessionButton hue={selectedVoice.hue} onStart={() => void voice.start()} onStop={voice.stop} status={voice.status} />
      <VoiceToolActivity activities={voice.toolActivities} />
    </section>
    {voice.error ? <p className={styles.error} role="alert">{voice.error}</p> : null}
    <VoiceAudioControls microphoneMuted={microphoneMuted} onMicrophoneMutedChange={setMicrophoneMuted} onSpeakerMutedChange={setSpeakerMuted} onVolumeChange={setVolume} speakerMuted={speakerMuted} volume={volume} />
    </>}</section>
    <ClientVoiceDrawer activeId={active.id} onClose={() => setDrawerOpen(false)} onDelete={deleteSession} onNew={createSession} onQueryChange={setQuery} onSelect={(id) => { voice.stop(); setActiveId(id); setDrawerOpen(false); setExpanded(false); }} open={drawerOpen} query={query} sessions={sessions} />
  </aside>;
}
