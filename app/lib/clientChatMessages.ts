import type { ClientChatMessage, ClientChatStreamEvent } from "../components/clientChatTypes";


export function applyClientChatEvent(messages: ClientChatMessage[], event: ClientChatStreamEvent): ClientChatMessage[] {
  if (event.type === "content") {
    const last = messages.at(-1);
    if (last?.kind === "message" && last.role === "assistant") {
      return messages.map((message, index) => index === messages.length - 1 ? { ...last, text: last.text + event.content } : message);
    }
    return [...messages, { id: crypto.randomUUID(), kind: "message", role: "assistant", text: event.content }];
  }
  if (event.type === "tool_call") {
    if (messages.some((message) => message.kind === "tool" && message.id === event.id)) return messages;
    return [...messages, { id: event.id, kind: "tool", name: event.name, status: "running" }];
  }
  if (event.type === "tool_response") {
    return messages.map((message) => message.kind === "tool" && message.id === event.id ? { ...message, name: event.name || message.name, status: event.status } : message);
  }
  if (event.type === "error") {
    return [...messages, { id: crypto.randomUUID(), kind: "message", role: "assistant", text: `Error: ${event.error}` }];
  }
  return messages;
}
