import type { ClientChatStreamEvent } from "../components/clientChatTypes";
import { authenticatedFetch } from "./authenticatedFetch";

export async function streamGoalsChat(options: { chatId: string; createTitle: boolean; message: string; signal: AbortSignal; onEvent: (event: ClientChatStreamEvent) => void }) {
  const response = await authenticatedFetch("/api/goals/chat/stream", {
    body: JSON.stringify({ chat_id: options.chatId, create_title: options.createTitle, message: options.message }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
    signal: options.signal,
  });
  if (!response.ok || !response.body) throw new Error("Goals chat failed");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) emit(frame, options.onEvent);
    if (done) break;
  }
  if (buffer.trim()) emit(buffer, options.onEvent);
}

function emit(frame: string, onEvent: (event: ClientChatStreamEvent) => void) {
  const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
  if (data) onEvent(JSON.parse(data) as ClientChatStreamEvent);
}
