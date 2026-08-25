import type { LucideIcon } from "lucide-react";
import { Blocks, BookOpenText, Bot, Building2, CircleDot, FileText, FolderGit2, GitBranch, GitPullRequest, Hash, ListTodo, MessageCircle, MessageSquareText, PanelsTopLeft } from "lucide-react";


export type PluginGroup = "productivity" | "developer" | "communication" | "automation";

export type PluginDefinition = {
  id: string;
  name: string;
  description: string;
  group: PluginGroup;
  color: string;
  icon: LucideIcon;
  logo?: string;
  permissions: string[];
  features?: Array<{ id: string; name: string; description: string; icon: LucideIcon }>;
};

export type PluginPermissionState = { id: string; name: string; description: string; enabled: boolean };

export type PluginState = {
  id: string;
  installed: boolean;
  connected: boolean;
  connection_type: "google" | "mcp" | "extension";
  connection_supported: boolean;
  setup_message?: string | null;
  account_label?: string | null;
  tool_count: number;
  repository_count?: number | null;
  permissions: PluginPermissionState[];
};

export const googleWorkspacePlugin: PluginDefinition = {
  id: "google-workspace",
  name: "Google Workspace",
  description: "Gmail, Drive, Calendar, Docs, Sheets, and more",
  group: "productivity",
  color: "#4285f4",
  icon: Blocks,
  permissions: ["Use the Workspace services you allow", "Keep access connected with an offline token"],
};

export const pluginDirectory: PluginDefinition[] = [
  googleWorkspacePlugin,
  { id: "github", name: "GitHub", description: "Work with repositories, issues, and pull requests", group: "developer", color: "#343431", icon: GitBranch, logo: "/github-142-svgrepo-com.svg", permissions: ["Read authorized repositories", "Create approved issues, comments, and pull requests"], features: [
    { id: "github.repositories", name: "Repositories", description: "Read and work with selected repositories", icon: FolderGit2 },
    { id: "github.issues", name: "Issues", description: "Read and update repository issues", icon: CircleDot },
    { id: "github.pull-requests", name: "Pull requests", description: "Read and work with pull requests", icon: GitPullRequest },
  ] },
  { id: "notion", name: "Notion", description: "Search and update connected Notion workspaces", group: "productivity", color: "#333330", icon: FileText, permissions: ["Search authorized pages", "Create and update workspace content"] },
  { id: "linear", name: "Linear", description: "Plan projects and manage issues", group: "productivity", color: "#675bd3", icon: CircleDot, logo: "/linear-svgrepo-com.svg", permissions: ["Read projects and issues", "Create and update approved work"] },
  { id: "atlassian", name: "Atlassian", description: "Work across Jira and Confluence", group: "productivity", color: "#1769e0", icon: Building2, logo: "/atlassian-svgrepo-com.svg", permissions: ["Read Jira and Confluence work", "Create approved issues, pages, and comments"], features: [
    { id: "atlassian.jira", name: "Jira", description: "Read and update Jira work", icon: ListTodo },
    { id: "atlassian.confluence", name: "Confluence", description: "Read and update Confluence pages", icon: BookOpenText },
  ] },
  { id: "vercel", name: "Vercel", description: "Inspect projects, deployments, and logs", group: "developer", color: "#252523", icon: Bot, logo: "/vercel-icon-svgrepo-com.svg", permissions: ["Read authorized projects", "Inspect deployments and runtime logs"] },
  { id: "slack", name: "Slack", description: "Search channels and work with messages", group: "communication", color: "#7b4ca0", icon: MessageCircle, logo: "/slack-svgrepo-com.svg", permissions: ["Search approved Slack content", "Draft and send approved messages"], features: [
    { id: "slack.channels", name: "Channels", description: "Search connected Slack channels", icon: Hash },
    { id: "slack.messages", name: "Messages", description: "Read and work with Slack messages", icon: MessageSquareText },
  ] },
  { id: "browser-use", name: "Browser Use", description: "Control Chrome through the Front Desk extension", group: "automation", color: "#30302e", icon: PanelsTopLeft, logo: "/browser-settings-svgrepo-com.svg", permissions: ["Use every normal Chrome tab and window", "Open, navigate, inspect, and close tabs", "Use Playwright browser, network, storage, download, and DevTools capabilities"] },
];

export const pluginGroups: Array<{ id: PluginGroup; label: string }> = [
  { id: "productivity", label: "Productivity" },
  { id: "developer", label: "Developer Tools" },
  { id: "communication", label: "Communication" },
  { id: "automation", label: "Computer Automation" },
];

export function pluginById(pluginId: string) {
  return pluginDirectory.find((plugin) => plugin.id === pluginId);
}
