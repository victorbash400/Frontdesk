import type { LucideIcon } from "lucide-react";
import { Blocks, Bot, Braces, Building2, CircleDot, FileText, GitBranch, MessageCircle, Search } from "lucide-react";


export type PluginGroup = "built-in" | "featured" | "productivity" | "developer" | "communication";

export type PluginDefinition = {
  id: string;
  name: string;
  description: string;
  group: PluginGroup;
  color: string;
  icon: LucideIcon;
  permissions: string[];
};

export type PluginState = {
  id: string;
  installed: boolean;
  connected: boolean;
  built_in: boolean;
  connection_supported: boolean;
  setup_message?: string | null;
  account_label?: string | null;
  tool_count: number;
};

export const pluginDirectory: PluginDefinition[] = [
  { id: "code", name: "Code", description: "Work with source code and project files", group: "built-in", color: "#4b63a8", icon: Braces, permissions: ["Read project files", "Create and update approved code"] },
  { id: "web-search", name: "Web Search", description: "Research current information on the web", group: "built-in", color: "#3279cf", icon: Search, permissions: ["Search the public web", "Open and read search results"] },
  { id: "github", name: "GitHub", description: "Work with repositories, issues, and pull requests", group: "featured", color: "#343431", icon: GitBranch, permissions: ["Read authorized repositories", "Create approved issues, comments, and pull requests"] },
  { id: "notion", name: "Notion", description: "Search and update connected Notion workspaces", group: "featured", color: "#333330", icon: FileText, permissions: ["Search authorized pages", "Create and update workspace content"] },
  { id: "linear", name: "Linear", description: "Plan projects and manage issues", group: "productivity", color: "#675bd3", icon: CircleDot, permissions: ["Read projects and issues", "Create and update approved work"] },
  { id: "atlassian", name: "Atlassian", description: "Work across Jira and Confluence", group: "productivity", color: "#1769e0", icon: Building2, permissions: ["Read Jira and Confluence work", "Create approved issues, pages, and comments"] },
  { id: "vercel", name: "Vercel", description: "Inspect projects, deployments, and logs", group: "developer", color: "#252523", icon: Bot, permissions: ["Read authorized projects", "Inspect deployments and runtime logs"] },
  { id: "slack", name: "Slack", description: "Search channels and work with messages", group: "communication", color: "#7b4ca0", icon: MessageCircle, permissions: ["Search approved Slack content", "Draft and send approved messages"] },
];

export const pluginGroups: Array<{ id: PluginGroup; label: string }> = [
  { id: "built-in", label: "Built in" },
  { id: "featured", label: "Featured" },
  { id: "productivity", label: "Productivity" },
  { id: "developer", label: "Developer Tools" },
  { id: "communication", label: "Communication" },
];

export const googleWorkspacePlugin: PluginDefinition = {
  id: "google-workspace",
  name: "Google Workspace",
  description: "Gmail, Drive, Calendar, Docs, Sheets, and more",
  group: "featured",
  color: "#4285f4",
  icon: Blocks,
  permissions: ["Use the Workspace services you allow", "Keep access connected with an offline token"],
};

export function pluginById(pluginId: string) {
  return pluginDirectory.find((plugin) => plugin.id === pluginId);
}
