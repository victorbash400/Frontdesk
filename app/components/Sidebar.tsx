import { BookOpenCheck, CircleAlert, Clock3, FileText, Folder, FolderPlus, Mail, Phone, Puzzle, Trash2, UsersRound, type LucideIcon } from "lucide-react";

import { locationLabels } from "../lib/fileSystemSelectors";
import type { Destination, SmartLocation } from "../types/filesystem";
import styles from "./Sidebar.module.css";

const sections: Array<{ label?: string; items: Array<{ location: SmartLocation; icon: LucideIcon }> }> = [
  { items: [{ location: "recents", icon: Clock3 }, { location: "shared", icon: UsersRound }] },
  { label: "Favorites", items: [{ location: "clients", icon: Folder }, { location: "needs-you", icon: CircleAlert }] },
  { label: "Locations", items: [{ location: "calls", icon: Phone }, { location: "email", icon: Mail }, { location: "documents", icon: FileText }, { location: "plugins", icon: Puzzle }, { location: "skills", icon: BookOpenCheck }, { location: "trash", icon: Trash2 }] },
];

type SidebarProps = {
  destination: Destination;
  onCreateClient: () => void;
  onNavigate: (location: SmartLocation) => void;
};

export function Sidebar({ destination, onCreateClient, onNavigate }: SidebarProps) {
  return (
    <aside className={styles.sidebar}>
      <nav aria-label="Filesystem locations">
        {sections.map((section) => (
          <section key={section.label ?? "primary"}>
            {section.label ? <h2>{section.label}</h2> : null}
            {section.label === "Favorites" ? (
              <button onClick={onCreateClient} type="button">
                <FolderPlus aria-hidden="true" />
                <span>New Client</span>
              </button>
            ) : null}
            {section.items.map(({ location, icon: Icon }) => {
              const active = destination.type === "location" && destination.location === location;
              return (
                <button aria-current={active ? "page" : undefined} key={location} onClick={() => onNavigate(location)} title={locationLabels[location]} type="button">
                  <Icon aria-hidden="true" />
                  <span>{locationLabels[location]}</span>
                </button>
              );
            })}
          </section>
        ))}
      </nav>
    </aside>
  );
}
