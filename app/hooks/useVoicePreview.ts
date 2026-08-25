"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { authenticatedFetch } from "../lib/authenticatedFetch";

export function useVoicePreview(clientId: string, sessionId: string) {
  const [previewing, setPreviewing] = useState(false);
  const [error, setError] = useState<string>();
  const socketRef = useRef<WebSocket | undefined>(undefined);
  const contextRef = useRef<AudioContext | undefined>(undefined);

  const stop = useCallback(() => {
    socketRef.current?.close(); socketRef.current = undefined;
    const context = contextRef.current; contextRef.current = undefined;
    if (context && context.state !== "closed") void context.close();
    setPreviewing(false);
  }, []);

  const preview = useCallback(async (voiceName: string) => {
    stop(); setPreviewing(true); setError(undefined);
    try {
      const previewSessionId = `${sessionId}-preview`;
      const response = await authenticatedFetch("/api/voice/ticket", { body: JSON.stringify({ client_id: clientId, session_id: previewSessionId }), headers: { "Content-Type": "application/json" }, method: "POST" });
      const payload = await response.json() as { ticket?: string; websocketUrl?: string; error?: string };
      if (!response.ok || !payload.ticket || !payload.websocketUrl) throw new Error(payload.error || "Voice preview authentication failed.");
      const context = new AudioContext(); contextRef.current = context;
      await context.audioWorklet.addModule("/audio-output-processor.js");
      const output = new AudioWorkletNode(context, "audio-output-processor"); output.connect(context.destination);
      await context.resume();
      const query = new URLSearchParams({ ticket: payload.ticket, voice: voiceName, language: "en" });
      const socket = new WebSocket(`${payload.websocketUrl}/api/voice/${encodeURIComponent(previewSessionId)}?${query}`); socket.binaryType = "arraybuffer"; socketRef.current = socket;
      socket.addEventListener("message", (event) => {
        if (event.data instanceof ArrayBuffer) { output.port.postMessage({ type: "audio", pcm: event.data }, [event.data]); return; }
        const message = JSON.parse(String(event.data)) as { type: string; error?: string };
        if (message.type === "ready") socket.send(JSON.stringify({ type: "preview" }));
        if (message.type === "turn_complete") output.port.postMessage({ type: "turn_complete" });
        if (message.type === "error") { setError(message.error || "Voice preview failed."); stop(); }
      });
      output.port.onmessage = ({ data }: MessageEvent<{ type: string }>) => { if (data.type === "drained") stop(); };
      socket.addEventListener("error", () => { setError("Could not play the voice preview."); stop(); }, { once: true });
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Voice preview failed."); stop(); }
  }, [clientId, sessionId, stop]);

  useEffect(() => stop, [stop]);
  return { error, preview, previewing, stop };
}
