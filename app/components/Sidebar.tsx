import { Clock3, FileText, Folder, FolderPlus, Mail, MessageSquareText, Phone, Share2, Trash2, UserRoundCheck } from "lucide-react";

import { locationLabels } from "../lib/fileSystemSelectors";
import type { Destination, SmartLocation } from "../types/filesystem";
import { CustomIcon } from "./CustomIcon";
import styles from "./Sidebar.module.css";

const sections: Array<{ label?: string; items: Array<{ location: SmartLocation; icon?: typeof Clock3; customIcon?: "plugin" | "skills" }> }> = [
  { items: [{ location: "recents", icon: Clock3 }, { location: "shared", icon: Share2 }] },
  { label: "Favorites", items: [{ location: "clients", icon: Folder }, { location: "needs-you", icon: UserRoundCheck }] },
  { label: "Locations", items: [{ location: "calls", icon: Phone }, { location: "email", icon: Mail }, { location: "documents", icon: FileText }, { location: "requests", icon: MessageSquareText }, { location: "plugins", customIcon: "plugin" }, { location: "skills", customIcon: "skills" }, { location: "trash", icon: Trash2 }] },
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
            {section.items.map(({ location, icon: Icon, customIcon }) => {
              const active = destination.type === "location" && destination.location === location;
              return (
                <button aria-current={active ? "page" : undefined} key={location} onClick={() => onNavigate(location)} title={locationLabels[location]} type="button">
                  {Icon ? <Icon aria-hidden="true" /> : <CustomIcon name={customIcon!} />}
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
