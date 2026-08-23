import { ChevronRight } from "lucide-react";

import type { BreadcrumbItem, Destination } from "../types/filesystem";
import styles from "./Breadcrumbs.module.css";

type BreadcrumbsProps = {
  className?: string;
  items: BreadcrumbItem[];
  onNavigate: (destination: Destination) => void;
};

export function Breadcrumbs({ className, items, onNavigate }: BreadcrumbsProps) {
  return (
    <nav aria-label="Breadcrumb" className={`${styles.breadcrumbs} ${className ?? ""}`}>
      {items.map((item, index) => {
        const current = index === items.length - 1;
        return (
          <span className={styles.crumb} key={`${item.destination.type}-${item.destination.type === "folder" ? item.destination.id : item.destination.location}`}>
            {index > 0 ? <ChevronRight aria-hidden="true" /> : null}
            {current ? <strong aria-current="page">{item.label}</strong> : <button onClick={() => onNavigate(item.destination)} type="button">{item.label}</button>}
          </span>
        );
      })}
    </nav>
  );
}
