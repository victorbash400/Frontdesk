import Image from "next/image";
import type { CSSProperties } from "react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import styles from "./PluginIcon.module.css";


type PluginIconProps = {
  plugin: PluginDefinition;
  variant?: "catalog" | "row" | "dialog" | "profile";
};

export function PluginIcon({ plugin, variant = "catalog" }: PluginIconProps) {
  const Icon = plugin.icon;
  return <span className={`${styles.icon} ${styles[variant]}`} style={{ "--plugin-color": plugin.color } as CSSProperties}>{plugin.logo ? <Image alt="" height={20} src={plugin.logo} width={20} /> : <Icon aria-hidden="true" />}</span>;
}
