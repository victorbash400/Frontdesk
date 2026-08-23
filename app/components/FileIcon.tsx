import { FileAudio, FileText, FileUser, ListTodo, Mail, MessageSquareText, NotebookPen } from "lucide-react";

import type { NodeKind } from "../types/filesystem";
import styles from "./FileIcon.module.css";

type FileIconProps = {
  kind: NodeKind;
  size?: "small" | "large";
};

export function FileIcon({ kind, size = "large" }: FileIconProps) {
  if (kind === "client" || kind === "folder") {
    return (
      <svg aria-hidden="true" className={styles.folder} data-size={size} viewBox="0 0 96 72">
        <defs>
          <linearGradient id="folder-face" x1="48" x2="48" y1="18" y2="66" gradientUnits="userSpaceOnUse">
            <stop stopColor="#63B9F8" />
            <stop offset="1" stopColor="#2489E8" />
          </linearGradient>
          <linearGradient id="folder-tab" x1="24" x2="24" y1="7" y2="27" gradientUnits="userSpaceOnUse">
            <stop stopColor="#62B8F7" />
            <stop offset="1" stopColor="#3397EC" />
          </linearGradient>
        </defs>
        <path d="M7 18.5A7.5 7.5 0 0 1 14.5 11h22.8c2.3 0 4.5 1.1 5.9 3l4.2 5.5H81a8 8 0 0 1 8 8V58a8 8 0 0 1-8 8H15a8 8 0 0 1-8-8V18.5Z" fill="url(#folder-tab)" />
        <path d="M7 27a8 8 0 0 1 8-8h66a8 8 0 0 1 8 8v31a8 8 0 0 1-8 8H15a8 8 0 0 1-8-8V27Z" fill="url(#folder-face)" />
        <path d="M11 29h74" stroke="#8ED0FF" strokeOpacity=".72" />
      </svg>
    );
  }

  const Icon = kind === "profile" ? FileUser : kind === "task" ? ListTodo : kind === "audio" ? FileAudio : kind === "email" ? Mail : kind === "request" ? MessageSquareText : kind === "note" ? NotebookPen : FileText;
  return <Icon aria-hidden="true" className={styles.file} data-size={size} />;
}
