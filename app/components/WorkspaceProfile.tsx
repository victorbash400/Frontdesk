"use client";

import { Eye, EyeOff } from "lucide-react";

import { googleWorkspacePlugin } from "../lib/pluginDirectory";
import { PluginRow } from "./PluginRow";


type WorkspaceProfileProps = {
  configured: boolean;
  connected: boolean;
  email?: string | null;
  needsReconnect: boolean;
  showEmail: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onEmailVisibilityChange: (visible: boolean) => void;
};

export function WorkspaceProfile({ configured, connected, email, needsReconnect, onConnect, onDisconnect, onEmailVisibilityChange, showEmail }: WorkspaceProfileProps) {
  const detail = connected || needsReconnect ? <>{showEmail ? email || "Connected account" : "Email hidden"}<button aria-label={showEmail ? "Hide email address" : "Show email address"} onClick={(event) => { event.stopPropagation(); onEmailVisibilityChange(!showEmail); }} type="button">{showEmail ? <Eye aria-hidden="true" /> : <EyeOff aria-hidden="true" />}</button>{needsReconnect ? " · Reconnect required" : ""}</> : configured ? googleWorkspacePlugin.description : "Google OAuth setup required";
  return <PluginRow detail={detail} disabled={!configured} disabledLabel={needsReconnect ? "Reconnect" : "Connect"} enabled={connected} onToggle={connected ? onDisconnect : onConnect} plugin={googleWorkspacePlugin} />;
}
