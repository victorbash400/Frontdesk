import type { ClientChat, ClientChatMessage } from "../components/clientChatTypes";
import { accountStorageKey } from "./accountStorage";


const storageNamespace = "operator-client-chats-v1";

export function loadClientChats(accountId: string, clientId: string): ClientChat[] {
  const stored = window.localStorage.getItem(storageKey(accountId, clientId));
  if (!stored) return [];
  const value: unknown = JSON.parse(stored);
  if (!Array.isArray(value) || !value.every(isChat)) throw new Error("The saved client chats are invalid.");
  return value.sort((left, right) => right.updatedAt - left.updatedAt);
}

export function saveClientChats(accountId: string, clientId: string, chats: ClientChat[]) {
  window.localStorage.setItem(storageKey(accountId, clientId), JSON.stringify(chats));
}

function storageKey(accountId: string, clientId: string) {
  if (!clientId.trim()) throw new Error("A client is required for chat.");
  return `${accountStorageKey(storageNamespace, accountId)}:${clientId}`;
}

function isChat(value: unknown): value is ClientChat {
  if (!value || typeof value !== "object") return false;
  const chat = value as Partial<ClientChat>;
  return typeof chat.createdAt === "number" && typeof chat.id === "string" && Array.isArray(chat.messages) && chat.messages.every(isMessage) && typeof chat.title === "string" && typeof chat.updatedAt === "number";
}

function isMessage(value: unknown): value is ClientChatMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as Partial<ClientChatMessage>;
  if (typeof message.id !== "string" || typeof message.kind !== "string") return false;
  if (message.kind === "message") return (message.role === "user" || message.role === "assistant") && typeof message.text === "string";
  return message.kind === "tool" && typeof message.name === "string" && (message.status === "running" || message.status === "done" || message.status === "error");
}
