import type { FileSystemData } from "../types/filesystem";

const storageKey = "operator-filesystem-v1";
const emptyFileSystem: FileSystemData = { version: 1, nodes: [] };

export function loadFileSystem(): FileSystemData {
  const stored = window.localStorage.getItem(storageKey);
  if (!stored) return emptyFileSystem;

  const data: unknown = JSON.parse(stored);
  if (!isFileSystemData(data)) {
    throw new Error("The saved Operator filesystem is invalid.");
  }

  const migrated = ensureClientProfiles(data);
  if (migrated !== data) saveFileSystem(migrated);
  return migrated;
}

function ensureClientProfiles(data: FileSystemData): FileSystemData {
  let changed = false;
  const nodes = [...data.nodes];
  for (const client of nodes.filter((node) => node.kind === "client")) {
    const existingIndex = nodes.findIndex((node) => node.parentId === client.id && node.name.trim().toLocaleLowerCase() === "client profile");
    if (existingIndex >= 0) {
      const existing = nodes[existingIndex];
      if (existing.kind !== "profile" || !existing.protected || existing.content === undefined) {
        nodes[existingIndex] = { ...existing, kind: "profile", protected: true, content: existing.content ?? "" };
        changed = true;
      }
      continue;
    }
    nodes.push(createClientProfile(client));
    changed = true;
  }
  return changed ? { ...data, nodes } : data;
}

function createClientProfile(client: FileSystemData["nodes"][number]) {
  return {
    id: crypto.randomUUID(),
    parentId: client.id,
    name: "Client Profile",
    kind: "profile" as const,
    createdAt: client.createdAt,
    updatedAt: client.updatedAt,
    tags: [],
    shared: false,
    needsAttention: false,
    trashedAt: client.trashedAt,
    content: "",
    protected: true,
  };
}

export function saveFileSystem(data: FileSystemData) {
  window.localStorage.setItem(storageKey, JSON.stringify(data));
}

function isFileSystemData(value: unknown): value is FileSystemData {
  if (!value || typeof value !== "object") return false;
  const data = value as Partial<FileSystemData>;
  return data.version === 1 && Array.isArray(data.nodes);
}
