export type VoiceTranscriptEntry = { id: string; role: "user" | "assistant"; sequence: number; text: string; final: boolean };
export type ClientVoiceSession = { id: string; createdAt: number; updatedAt: number; transcript: VoiceTranscriptEntry[] };
export type VoiceToolActivity = { id: string; name: string; args: Record<string, unknown>; status: "running" | "done" | "error"; error?: string };
