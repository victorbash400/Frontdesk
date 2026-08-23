import type { Destination, FileSystemNode, SmartLocation, SortMode, TagName } from "../types/filesystem";

const folderKinds = new Set(["client", "folder"]);

export function isContainer(node: FileSystemNode) {
  return folderKinds.has(node.kind);
}

export function nodesForDestination(nodes: FileSystemNode[], destination: Destination, selectedTag?: TagName) {
  let visible: FileSystemNode[];

  if (destination.type === "folder") {
    visible = nodes.filter((node) => node.parentId === destination.id && !node.trashedAt);
  } else {
    visible = nodesForLocation(nodes, destination.location);
  }

  return selectedTag ? visible.filter((node) => node.tags.includes(selectedTag)) : visible;
}

export function sortNodes(nodes: FileSystemNode[], sort: SortMode) {
  return [...nodes].sort((left, right) => {
    if (sort === "name-asc") return left.name.localeCompare(right.name, undefined, { numeric: true });
    if (sort === "name-desc") return right.name.localeCompare(left.name, undefined, { numeric: true });
    if (sort === "date-asc") return left.updatedAt.localeCompare(right.updatedAt);
    return right.updatedAt.localeCompare(left.updatedAt);
  });
}

export function destinationTitle(nodes: FileSystemNode[], destination: Destination) {
  if (destination.type === "location") return locationLabels[destination.location];
  return nodes.find((node) => node.id === destination.id)?.name ?? "Clients";
}

export function folderPath(nodes: FileSystemNode[], folderId: string) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const path: FileSystemNode[] = [];
  let current = byId.get(folderId);

  while (current) {
    path.unshift(current);
    current = current.parentId ? byId.get(current.parentId) : undefined;
  }

  return path;
}

function nodesForLocation(nodes: FileSystemNode[], location: SmartLocation) {
  if (location === "clients") return nodes.filter((node) => node.kind === "client" && !node.trashedAt);
  if (location === "trash") return nodes.filter((node) => Boolean(node.trashedAt));

  const active = nodes.filter((node) => !node.trashedAt);
  if (location === "recents") return active;
  if (location === "shared") return active.filter((node) => node.shared);
  if (location === "needs-you") return active.filter((node) => node.needsAttention);
  if (location === "calls") return active.filter((node) => node.kind === "audio");
  if (location === "email") return active.filter((node) => node.kind === "email");
  if (location === "documents") return active.filter((node) => node.kind === "document" || node.kind === "note");
  if (location === "requests") return active.filter((node) => node.kind === "request");
  return [];
}

export const locationLabels: Record<SmartLocation, string> = {
  clients: "Clients",
  recents: "Recents",
  shared: "Shared",
  "needs-you": "Needs You",
  calls: "Calls",
  email: "Email",
  documents: "Documents",
  requests: "Requests",
  trash: "Trash",
  plugins: "Plugins",
  skills: "Skills",
};
