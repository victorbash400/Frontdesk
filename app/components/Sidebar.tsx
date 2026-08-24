import { BookOpenCheck, Command, FileText, Folder, FolderPlus, ListTodo, Mail, Phone, Puzzle, Target, Trash2, type LucideIcon } from "lucide-react";

import { locationLabels } from "../lib/fileSystemSelectors";
import type { Destination, SmartLocation } from "../types/filesystem";
import { AccountButton } from "./AccountButton";
import styles from "./Sidebar.module.css";

const clientItems: Array<{ location: SmartLocation; icon: LucideIcon }> = [
  { location: "clients", icon: Folder },
];

const workspaceItems: Array<{ location: SmartLocation; icon: LucideIcon }> = [
  { location: "tasks", icon: ListTodo },
  { location: "goals", icon: Target },
  { location: "calls", icon: Phone },
  { location: "emails", icon: Mail },
  { location: "documents", icon: FileText },
  { location: "plugins", icon: Puzzle },
  { location: "skills", icon: BookOpenCheck },
  { location: "trash", icon: Trash2 },
];

type SidebarProps = {
  account: { email: string; name: string };
  destination: Destination;
  onCreateClient: () => void;
  onNavigate: (destination: Destination) => void;
};

export function Sidebar({ account, destination, onCreateClient, onNavigate }: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <header>
        <Command aria-hidden="true" />
        <strong>Front Desk</strong>
        <AccountButton email={account.email} name={account.name} />
      </header>
      <nav aria-label="Filesystem locations">
        <button onClick={onCreateClient} type="button">
          <FolderPlus aria-hidden="true" />
          <span>New Client</span>
        </button>
        <p>Client</p>
        {clientItems.map(({ location, icon }) => (
          <DestinationButton active={destination.type === "folder" || destination.type === "location" && destination.location === location} icon={icon} key={location} label={locationLabels[location]} onClick={() => onNavigate({ type: "location", location })} />
        ))}
        <p>Workspace</p>
        {workspaceItems.map(({ location, icon }) => (
          <DestinationButton active={destination.type === "location" && destination.location === location} icon={icon} key={location} label={locationLabels[location]} onClick={() => onNavigate({ type: "location", location })} />
        ))}
      </nav>
    </aside>
  );
}

type DestinationButtonProps = {
  active: boolean;
  icon: LucideIcon;
  label: string;
  onClick: () => void;
};

function DestinationButton({ active, icon: Icon, label, onClick }: DestinationButtonProps) {
  return (
    <button aria-current={active ? "page" : undefined} onClick={onClick} title={label} type="button">
      <Icon aria-hidden="true" />
      <span>{label}</span>
    </button>
  );
}
