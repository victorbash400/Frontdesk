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

  return data;
}

export function saveFileSystem(data: FileSystemData) {
  window.localStorage.setItem(storageKey, JSON.stringify(data));
}

function isFileSystemData(value: unknown): value is FileSystemData {
  if (!value || typeof value !== "object") return false;
  const data = value as Partial<FileSystemData>;
  return data.version === 1 && Array.isArray(data.nodes);
}
