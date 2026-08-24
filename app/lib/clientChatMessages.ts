import type { ClientChatMessage, ClientChatStreamEvent } from "../components/clientChatTypes";


export function applyClientChatEvent(messages: ClientChatMessage[], event: ClientChatStreamEvent): ClientChatMessage[] {
  if (event.type === "done" || event.type === "title") return finishReasoning(messages);
  if (event.type === "reasoning") {
    const last = messages.at(-1);
    if (last?.kind === "reasoning") {
      return messages.map((message, index) => index === messages.length - 1 ? { ...last, text: last.text + event.content } : message);
    }
    return [...messages, { id: crypto.randomUUID(), kind: "reasoning", text: event.content, startedAt: Date.now() }];
  }
  if (event.type === "content") {
    const finished = finishReasoning(messages);
    const last = finished.at(-1);
    if (last?.kind === "message" && last.role === "assistant") {
      return finished.map((message, index) => index === finished.length - 1 ? { ...last, text: last.text + event.content } : message);
    }
    return [...finished, { id: crypto.randomUUID(), kind: "message", role: "assistant", text: event.content }];
  }
  if (event.type === "tool_call") {
    const finished = finishReasoning(messages);
    if (finished.some((message) => message.kind === "tool" && message.id === event.id)) return finished;
    return [...finished, { id: event.id, kind: "tool", name: event.name, status: "running" }];
  }
  if (event.type === "tool_response") {
    return messages.map((message) => message.kind === "tool" && message.id === event.id ? { ...message, name: event.name || message.name, status: event.status } : message);
  }
  if (event.type === "error") {
    return [...finishReasoning(messages), { id: crypto.randomUUID(), kind: "message", role: "assistant", text: `Error: ${event.error}` }];
  }
  return messages;
}

function finishReasoning(messages: ClientChatMessage[]) {
  const now = Date.now();
  return messages.map((message) => message.kind === "reasoning" && !message.finishedAt ? { ...message, finishedAt: now } : message);
}
