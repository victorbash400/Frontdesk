export type ClientChatMessage =
  | { id: string; kind: "message"; role: "user" | "assistant"; text: string }
  | { id: string; kind: "tool"; label: string; status: "running" | "complete" | "error" };

export type ClientChat = {
  id: string;
  title: string;
  messages: ClientChatMessage[];
};
