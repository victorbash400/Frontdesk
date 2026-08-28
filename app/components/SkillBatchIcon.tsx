import Image from "next/image";
import { Layers3, UserRoundPen } from "lucide-react";

import type { PluginDefinition } from "../lib/pluginDirectory";
import styles from "./SkillBatchIcon.module.css";

export function SkillBatchIcon({ plugin, title }: { plugin?: PluginDefinition; title: string }) {
  if (title === "AquaLabs") return <span className={styles.icon}><Image alt="" height={18} src="/aqualabs-icon.png" width={18} /></span>;
  const Icon = plugin?.icon || (title === "Created by you" ? UserRoundPen : Layers3);
  return <span className={styles.icon} style={plugin ? { color: plugin.color } : undefined}>{plugin?.logo ? <Image alt="" height={18} src={plugin.logo} width={18} /> : <Icon aria-hidden="true" />}</span>;
}
