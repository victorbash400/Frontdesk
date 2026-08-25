"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { authenticatedFetch } from "../lib/authenticatedFetch";
import type { VoiceToolActivity, VoiceTranscriptEntry } from "../types/voice";

export type VoiceStatus = "idle" | "connecting" | "listening" | "speaking" | "error";

export function useVoiceSession({ clientId, microphoneMuted, onTranscript, sessionId, speakerMuted, volume, voiceName }: { clientId: string; microphoneMuted: boolean; onTranscript: (entry: VoiceTranscriptEntry) => void; sessionId: string; speakerMuted: boolean; volume: number; voiceName: string }) {
  const [status, setStatus] = useState<VoiceStatus>("idle");
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string>();
  const [toolActivities, setToolActivities] = useState<VoiceToolActivity[]>([]);
  const socketRef = useRef<WebSocket | undefined>(undefined);
  const streamRef = useRef<MediaStream | undefined>(undefined);
  const contextRef = useRef<AudioContext | undefined>(undefined);
  const inputRef = useRef<AudioWorkletNode | undefined>(undefined);
  const outputRef = useRef<AudioWorkletNode | undefined>(undefined);
  const gainRef = useRef<GainNode | undefined>(undefined);
  const mutedRef = useRef(microphoneMuted);
  useEffect(() => { mutedRef.current = microphoneMuted; }, [microphoneMuted]);

  const stop = useCallback(() => {
    socketRef.current?.close(); socketRef.current = undefined;
    inputRef.current?.disconnect(); inputRef.current = undefined;
    outputRef.current?.disconnect(); outputRef.current = undefined;
    streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = undefined;
    const context = contextRef.current; contextRef.current = undefined; gainRef.current = undefined;
    if (context && context.state !== "closed") void context.close();
    setAudioLevel(0); setToolActivities([]); setStatus("idle");
  }, []);

  const start = useCallback(async () => {
    if (status !== "idle" && status !== "error") return;
    setStatus("connecting"); setError(undefined);
    try {
      const ticketResponse = await authenticatedFetch("/api/voice/ticket", { body: JSON.stringify({ client_id: clientId, session_id: sessionId }), headers: { "Content-Type": "application/json" }, method: "POST" });
      const ticketPayload = await ticketResponse.json() as { ticket?: string; websocketUrl?: string; error?: string };
      if (!ticketResponse.ok || !ticketPayload.ticket || !ticketPayload.websocketUrl) throw new Error(ticketPayload.error || "Voice authentication failed.");
      const context = new AudioContext(); contextRef.current = context;
      const gain = context.createGain(); gain.gain.value = speakerMuted ? 0 : volume / 100; gain.connect(context.destination); gainRef.current = gain;
      await context.audioWorklet.addModule("/audio-output-processor.js");
      const output = new AudioWorkletNode(context, "audio-output-processor"); output.connect(gain); outputRef.current = output;
      output.port.onmessage = ({ data }: MessageEvent<{ type: string }>) => { if (data.type === "drained" && socketRef.current?.readyState === WebSocket.OPEN) socketRef.current.send(JSON.stringify({ type: "playback_drained" })); };
      await context.resume();
      const query = new URLSearchParams({ ticket: ticketPayload.ticket, voice: voiceName, language: "en" });
      const socket = new WebSocket(`${ticketPayload.websocketUrl}/api/voice/${encodeURIComponent(sessionId)}?${query}`); socket.binaryType = "arraybuffer"; socketRef.current = socket;
      await new Promise<void>((resolve, reject) => {
        const failed = () => reject(new Error("Could not connect to Front Desk voice."));
        const ready = (event: MessageEvent) => {
          if (typeof event.data !== "string") return;
          const message = JSON.parse(event.data) as { type: string; error?: string };
          if (message.type === "ready") { socket.removeEventListener("message", ready); resolve(); }
          if (message.type === "error") { socket.removeEventListener("message", ready); reject(new Error(message.error || "Front Desk voice failed.")); }
        };
        socket.addEventListener("message", ready); socket.addEventListener("error", failed, { once: true });
      });
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { autoGainControl: true, echoCancellation: true, noiseSuppression: true } }); streamRef.current = stream;
      await context.audioWorklet.addModule("/audio-input-processor.js");
      const source = context.createMediaStreamSource(stream); const input = new AudioWorkletNode(context, "audio-input-processor"); const silent = context.createGain(); silent.gain.value = 0; source.connect(input); input.connect(silent).connect(context.destination); inputRef.current = input;
      input.port.onmessage = (event: MessageEvent<ArrayBuffer>) => { if (!mutedRef.current && socket.readyState === WebSocket.OPEN) socket.send(event.data); };
      socket.addEventListener("message", (event) => {
        if (event.data instanceof ArrayBuffer) {
          const pcm = new Int16Array(event.data); let sum = 0; for (const sample of pcm) sum += (sample / 32768) ** 2;
          setAudioLevel(Math.min(1, Math.sqrt(sum / Math.max(1, pcm.length)) * 4)); output.port.postMessage({ type: "audio", pcm: event.data }, [event.data]); setStatus("speaking"); return;
        }
        const message = JSON.parse(String(event.data)) as { type: string; id?: string; name?: string; args?: Record<string, unknown>; result?: { status?: string; error?: string }; role?: VoiceTranscriptEntry["role"]; sequence?: number; text?: string; final?: boolean; error?: string };
        if (message.type === "interrupted") { output.port.postMessage({ type: "reset" }); setStatus("listening"); setAudioLevel(0); }
        if (message.type === "turn_complete") { output.port.postMessage({ type: "turn_complete" }); setStatus("listening"); setAudioLevel(0); window.setTimeout(() => setToolActivities([]), 1200); }
        if (message.type === "transcript_update" && message.id && message.role && typeof message.sequence === "number") onTranscript({ id: message.id, role: message.role, sequence: message.sequence, text: message.text || "", final: Boolean(message.final) });
        if (message.type === "tool_call" && message.id && message.name) setToolActivities([{ id: message.id, name: message.name, args: message.args || {}, status: "running" }]);
        if (message.type === "tool_response" && message.id) setToolActivities((items) => items.map((item) => item.id === message.id ? { ...item, status: message.result?.status === "failed" ? "error" : "done", error: message.result?.error } : item));
        if (message.type === "error") { setError(message.error || "Front Desk voice failed."); setStatus("error"); }
      });
      socket.addEventListener("close", () => { if (socketRef.current === socket) stop(); });
      setStatus("listening");
    } catch (reason) { stop(); setError(reason instanceof Error ? reason.message : "Front Desk voice failed."); setStatus("error"); }
  }, [clientId, onTranscript, sessionId, speakerMuted, status, stop, voiceName, volume]);

  useEffect(() => { if (gainRef.current) gainRef.current.gain.value = speakerMuted ? 0 : volume / 100; }, [speakerMuted, volume]);
  useEffect(() => stop, [stop]);
  return { audioLevel, error, start, status, stop, toolActivities };
}
