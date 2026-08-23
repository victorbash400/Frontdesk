import type { LucideIcon } from "lucide-react";
import { Blocks, CalendarDays, Cloud, Database, FileText, GitBranch, HardDrive, Mail, MessageCircle, Search, Webhook, Workflow } from "lucide-react";

export type PluginCategory = "plugins" | "apps" | "mcps";

export type PluginDefinition = {
  id: string;
  name: string;
  description: string;
  category: PluginCategory;
  color: string;
  icon: LucideIcon;
};

export const pluginDirectory: PluginDefinition[] = [
  { id: "gmail", name: "Gmail", description: "Read, organize, and draft client email", category: "apps", color: "#d94b45", icon: Mail },
  { id: "google-drive", name: "Google Drive", description: "Work with client files across Drive", category: "apps", color: "#2d78d4", icon: HardDrive },
  { id: "slack", name: "Slack", description: "Follow client channels and conversations", category: "apps", color: "#7b4ca0", icon: MessageCircle },
  { id: "calendar", name: "Google Calendar", description: "Schedule meetings and track commitments", category: "apps", color: "#3d7ddd", icon: CalendarDays },
  { id: "notion", name: "Notion", description: "Search and update shared workspaces", category: "plugins", color: "#333330", icon: FileText },
  { id: "hubspot", name: "HubSpot", description: "Manage contacts, companies, and deals", category: "plugins", color: "#e56c3d", icon: Database },
  { id: "salesforce", name: "Salesforce", description: "Connect client records and activity", category: "plugins", color: "#278acb", icon: Cloud },
  { id: "github", name: "GitHub", description: "Read repositories, issues, and pull requests", category: "plugins", color: "#343431", icon: GitBranch },
  { id: "web-search", name: "Web Search", description: "Research current information on the web", category: "plugins", color: "#3279cf", icon: Search },
  { id: "dropbox", name: "Dropbox", description: "Open and organize shared client files", category: "plugins", color: "#2877df", icon: HardDrive },
  { id: "asana", name: "Asana", description: "Track client projects and assigned work", category: "plugins", color: "#d75a68", icon: Workflow },
  { id: "airtable", name: "Airtable", description: "Read and update structured client records", category: "plugins", color: "#e4a52c", icon: Database },
  { id: "linear", name: "Linear", description: "Follow product issues and project cycles", category: "plugins", color: "#675bd3", icon: Blocks },
  { id: "zoom", name: "Zoom", description: "Access scheduled client meetings", category: "plugins", color: "#3976e9", icon: CalendarDays },
  { id: "client-data", name: "Client Data MCP", description: "Connect approved client data sources", category: "mcps", color: "#2e8c78", icon: Blocks },
  { id: "webhooks", name: "Webhook MCP", description: "Receive signed events from external tools", category: "mcps", color: "#9765bb", icon: Webhook },
  { id: "workflows", name: "Workflow MCP", description: "Run approved multi-step client workflows", category: "mcps", color: "#bc7348", icon: Workflow },
];

export const pluginPermissions: Record<string, string[]> = {
  gmail: ["Read client email", "Create drafts and organize messages"],
  "google-drive": ["Read selected files", "Create and update shared documents"],
  slack: ["Read selected channels", "Draft and send approved messages"],
  calendar: ["Read calendars", "Create and update approved events"],
  notion: ["Read selected workspaces", "Create and update pages"],
  hubspot: ["Read contacts and companies", "Update approved CRM records"],
  salesforce: ["Read client records", "Update approved activity"],
  github: ["Read repositories and issues", "Create approved issues and comments"],
  "web-search": ["Search the public web", "Open and read search results"],
  dropbox: ["Read selected folders", "Create and update shared files"],
  asana: ["Read projects and tasks", "Create and update assigned work"],
  airtable: ["Read selected bases", "Create and update records"],
  linear: ["Read teams and issues", "Create and update approved issues"],
  zoom: ["Read scheduled meetings", "Access approved meeting details"],
  "client-data": ["Read approved client sources", "Use data inside client tasks"],
  webhooks: ["Receive signed external events", "Attach events to the correct client"],
  workflows: ["Run approved workflows", "Read workflow results"],
};
