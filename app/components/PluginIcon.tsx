import Image from "next/image";

import type { PluginDefinition } from "../lib/pluginDirectory";
import styles from "./PluginIcon.module.css";


export function PluginIcon({ plugin }: { plugin: PluginDefinition }) {
  const Icon = plugin.icon;
  return <span className={styles.icon} style={{ "--plugin-color": plugin.color } as React.CSSProperties}>{plugin.logo ? <Image alt="" height={20} src={plugin.logo} width={20} /> : <Icon aria-hidden="true" />}</span>;
}
