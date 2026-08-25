import type { ClientVoiceSession } from "../types/voice";

const key = (accountId: string, clientId: string) => `front-desk:voice:${accountId}:${clientId}`;

export function loadClientVoiceSessions(accountId: string, clientId: string): ClientVoiceSession[] {
  try {
    const value = JSON.parse(window.localStorage.getItem(key(accountId, clientId)) || "[]");
    return Array.isArray(value) ? value : [];
  } catch { return []; }
}

export function saveClientVoiceSessions(accountId: string, clientId: string, sessions: ClientVoiceSession[]) {
  window.localStorage.setItem(key(accountId, clientId), JSON.stringify(sessions));
}
