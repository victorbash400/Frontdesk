import type { ClientChatStreamEvent } from "../components/clientChatTypes";


type StreamClientChatOptions = {
  chatId: string;
  clientId: string;
  createTitle: boolean;
  message: string;
  signal: AbortSignal;
  onEvent: (event: ClientChatStreamEvent) => void;
};

export async function streamClientChat(options: StreamClientChatOptions) {
  const response = await fetch("/api/chat/stream", {
    body: JSON.stringify({ chat_id: options.chatId, client_id: options.clientId, create_title: options.createTitle, message: options.message }),
    headers: { "Content-Type": "application/json" },
    method: "POST",
    signal: options.signal,
  });
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => ({ error: "Operator chat failed" })) as { error?: string };
    throw new Error(body.error || "Operator chat failed");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() || "";
    for (const frame of frames) emitFrame(frame, options.onEvent);
    if (done) break;
  }
  if (buffer.trim()) emitFrame(buffer, options.onEvent);
}

function emitFrame(frame: string, onEvent: (event: ClientChatStreamEvent) => void) {
  const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trimStart()).join("\n");
  if (data) onEvent(JSON.parse(data) as ClientChatStreamEvent);
}
