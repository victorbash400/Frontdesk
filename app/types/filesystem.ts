export const tagColors = {
  red: "#ff5f57",
  orange: "#ff9f0a",
  yellow: "#ffd60a",
  green: "#30d158",
  blue: "#0a84ff",
  purple: "#bf5af2",
  gray: "#98989d",
} as const;

export type TagName = keyof typeof tagColors;
export type NodeKind = "client" | "folder" | "audio" | "email" | "document" | "request" | "note";
export type ViewMode = "icons" | "list" | "columns" | "gallery";
export type SortMode = "name-asc" | "name-desc" | "date-desc" | "date-asc";
export type SmartLocation = "clients" | "recents" | "shared" | "needs-you" | "calls" | "email" | "documents" | "trash" | "plugins" | "skills";

export type FileSystemNode = {
  id: string;
  parentId: string | null;
  name: string;
  kind: NodeKind;
  createdAt: string;
  updatedAt: string;
  tags: TagName[];
  shared: boolean;
  needsAttention: boolean;
  trashedAt: string | null;
};

export type Destination =
  | { type: "location"; location: SmartLocation }
  | { type: "folder"; id: string };

export type BreadcrumbItem = {
  label: string;
  destination: Destination;
};

export type FileSystemData = {
  version: 1;
  nodes: FileSystemNode[];
};
