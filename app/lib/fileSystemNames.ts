import type { FileSystemNode } from "../types/filesystem";

export function hasSiblingName(nodes: FileSystemNode[], name: string, parentId: string | null, excludedId?: string) {
  const candidate = normalizeName(name);
  return nodes.some((node) => node.id !== excludedId && !node.trashedAt && node.parentId === parentId && normalizeName(node.name) === candidate);
}

function normalizeName(name: string) {
  return name.trim().normalize("NFKC").toLocaleLowerCase();
}
