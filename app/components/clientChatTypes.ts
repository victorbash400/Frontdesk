export type ClientChatMessage =
  | { id: string; kind: "message"; role: "user" | "assistant"; text: string }
  | { id: string; kind: "reasoning"; text: string; startedAt?: number; finishedAt?: number }
  | { id: string; kind: "tool"; name: string; status: "running" | "done" | "error" };

export type ClientChat = {
  createdAt: number;
  id: string;
  title: string;
  messages: ClientChatMessage[];
  updatedAt: number;
};

export type ClientChatStreamEvent =
  | { type: "content"; content: string }
  | { type: "reasoning"; content: string }
  | { type: "tool_call"; id: string; name: string; args: Record<string, unknown> }
  | { type: "tool_response"; id: string; name: string; status: "done" | "error" }
  | { type: "title"; title: string }
  | { type: "error"; error: string }
  | { type: "done" };
