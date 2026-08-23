import { BookOpenCheck, CircleAlert, Command, FileText, Folder, FolderPlus, Mail, Phone, Puzzle, Trash2, type LucideIcon } from "lucide-react";

import { locationLabels } from "../lib/fileSystemSelectors";
import type { Destination, SmartLocation } from "../types/filesystem";
import styles from "./Sidebar.module.css";

const items: Array<{ location: SmartLocation; icon: LucideIcon }> = [
  { location: "clients", icon: Folder },
  { location: "needs-you", icon: CircleAlert },
  { location: "calls", icon: Phone },
  { location: "email", icon: Mail },
  { location: "documents", icon: FileText },
  { location: "plugins", icon: Puzzle },
  { location: "skills", icon: BookOpenCheck },
  { location: "trash", icon: Trash2 },
];

type SidebarProps = {
  destination: Destination;
  onCreateClient: () => void;
  onNavigate: (location: SmartLocation) => void;
};

export function Sidebar({ destination, onCreateClient, onNavigate }: SidebarProps) {
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
        {items.map(({ location, icon: Icon }) => {
          const active = destination.type === "location" && destination.location === location;
          return (
            <button aria-current={active ? "page" : undefined} key={location} onClick={() => onNavigate(location)} title={locationLabels[location]} type="button">
              <Icon aria-hidden="true" />
              <span>{locationLabels[location]}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
