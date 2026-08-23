import { BookOpenCheck, CircleAlert, Command, FileText, Folder, FolderPlus, ListTodo, Mail, Phone, Puzzle, Trash2, type LucideIcon } from "lucide-react";

import { locationLabels } from "../lib/fileSystemSelectors";
import type { ClientLocation, Destination, SmartLocation } from "../types/filesystem";
import styles from "./Sidebar.module.css";

const rootItems: Array<{ location: SmartLocation; icon: LucideIcon }> = [
  { location: "clients", icon: Folder },
  { location: "needs-you", icon: CircleAlert },
  { location: "tasks", icon: ListTodo },
  { location: "calls", icon: Phone },
  { location: "emails", icon: Mail },
  { location: "documents", icon: FileText },
  { location: "plugins", icon: Puzzle },
  { location: "skills", icon: BookOpenCheck },
  { location: "trash", icon: Trash2 },
];

const clientItems: Array<{ location: ClientLocation; icon: LucideIcon }> = [
  { location: "tasks", icon: ListTodo },
  { location: "calls", icon: Phone },
  { location: "emails", icon: Mail },
  { location: "documents", icon: FileText },
];

const workspaceItems: Array<{ location: SmartLocation; icon: LucideIcon }> = [
  { location: "needs-you", icon: CircleAlert },
  { location: "plugins", icon: Puzzle },
  { location: "skills", icon: BookOpenCheck },
  { location: "trash", icon: Trash2 },
];

type SidebarProps = {
  client?: { id: string; name: string };
  destination: Destination;
  onCreateClient: () => void;
  onNavigate: (destination: Destination) => void;
};

export function Sidebar({ client, destination, onCreateClient, onNavigate }: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <header>
        <Command aria-hidden="true" />
        <strong>Operator</strong>
      </header>
      <nav aria-label="Filesystem locations">
        <button onClick={onCreateClient} type="button">
          <FolderPlus aria-hidden="true" />
          <span>New Client</span>
        </button>
        {client ? (
          <>
            <p>Client</p>
            <DestinationButton active={destination.type === "folder" && destination.id === client.id} icon={Folder} label={client.name} onClick={() => onNavigate({ type: "folder", id: client.id })} />
            {clientItems.map(({ location, icon }) => (
              <DestinationButton active={destination.type === "client-location" && destination.clientId === client.id && destination.location === location} icon={icon} key={location} label={locationLabels[location]} onClick={() => onNavigate({ type: "client-location", clientId: client.id, location })} />
            ))}
            <p>Workspace</p>
            {workspaceItems.map(({ location, icon }) => (
              <DestinationButton active={destination.type === "location" && destination.location === location} icon={icon} key={location} label={locationLabels[location]} onClick={() => onNavigate({ type: "location", location })} />
            ))}
          </>
        ) : rootItems.map(({ location, icon }) => (
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
