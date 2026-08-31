import type { FileSystemData } from "../types/filesystem";
import { accountStorageKey } from "./accountStorage";

const storageNamespace = "front-desk-filesystem-v2";
const emptyFileSystem: FileSystemData = { version: 1, nodes: [] };

export function loadFileSystem(accountId: string): FileSystemData {
  const stored = window.localStorage.getItem(accountStorageKey(storageNamespace, accountId));
  if (!stored) return emptyFileSystem;

  const data: unknown = JSON.parse(stored);
  if (!isFileSystemData(data)) {
    throw new Error("The saved Operator filesystem is invalid.");
  }

  const migrated = ensurePotatoDocuments(ensureClientProfiles(data));
  if (migrated !== data) saveFileSystem(accountId, migrated);
  return migrated;
}

function ensurePotatoDocuments(data: FileSystemData): FileSystemData {
  const potato = data.nodes.find((node) => node.kind === "client" && node.name.trim().toLocaleLowerCase() === "potato" && !node.trashedAt);
  if (!potato) return data;
  const existing = new Set(data.nodes.filter((node) => node.parentId === potato.id).map((node) => node.name.toLocaleLowerCase()));
  const timestamp = new Date().toISOString();
  const documents = potatoDocuments.filter((document) => !existing.has(document.name.toLocaleLowerCase())).map((document) => ({
    id: crypto.randomUUID(),
    parentId: potato.id,
    name: document.name,
    kind: "document" as const,
    createdAt: timestamp,
    updatedAt: timestamp,
    tags: [],
    shared: false,
    needsAttention: false,
    trashedAt: null,
    content: document.content,
  }));
  return documents.length ? { ...data, nodes: [...data.nodes, ...documents] } : data;
}

const potatoDocuments = [
  {
    name: "Portal access recovery.md",
    content: `# Potato portal access recovery

## Customer
Potato Foods Ltd

## Known issue
Users migrated from the legacy wholesale portal can enter a redirect loop after signing in. The account is active; the loop is caused by a stale organization assignment, not an incorrect password.

## Verified resolution
1. Confirm the caller's company email and billing postcode. Never ask for a password or one-time code.
2. Set the organization assignment to POTATO-NA-204.
3. Ask the customer to open a private browser window and visit https://portal.example.test/sign-in.
4. The first successful sign-in prompts the customer to create a new passkey.

## Escalation
If the redirect remains after reassignment, attach incident code PT-ACCESS-204 and escalate to Identity Operations. Target response: 30 minutes during business hours.

## Agent guardrail
Explain each change before updating the client's goal board. Obtain confirmation before recording the issue as resolved.`,
  },
  {
    name: "Order POT-48291 delivery incident.md",
    content: `# Order POT-48291 delivery incident

## Summary
Potato Foods Ltd ordered 48 refrigerated produce crates for the Westlands distribution site. Twelve crates missed the 24 August delivery window after carrier vehicle KDA-771Q failed inspection.

## Current status
- 36 crates delivered and accepted.
- 12 replacement crates reserved under shipment PT-RPL-7712.
- Replacement delivery window: 27 August, 08:00–10:00 EAT.
- Carrier tracking reference: COLDCHAIN-90318.

## Approved remedy
The account manager may apply a 7.5% service credit to the delayed portion after the customer confirms receipt. Do not credit the complete order.

## Next action
Confirm the receiving contact will be present, then record delivery confirmation and the approved partial credit on the goal board.`,
  },
  {
    name: "Service agreement and escalation contacts.md",
    content: `# Potato service agreement and escalation contacts

## Support coverage
Priority support runs Monday–Saturday, 07:00–19:00 EAT. Severity-one incidents receive an initial response within 30 minutes; severity-two incidents within two business hours.

## Authorized contacts
- Amina Otieno — Operations Director — may approve delivery changes and service credits up to 10%.
- Daniel Mwangi — Finance Lead — may discuss invoices and payment allocation.
- Ruth Njeri — Site Manager — may confirm deliveries but cannot approve credits.

## Communication policy
Send operational summaries to the client's Front Desk message inbox. Do not disclose internal incident notes, employee phone numbers, credentials, authentication codes, or unrelated customer data.

## Closure standard
A case is complete only after the customer confirms the outcome, the relevant goal is updated, and a concise written summary is sent.`,
  },
];

function ensureClientProfiles(data: FileSystemData): FileSystemData {
  let changed = false;
  const nodes = [...data.nodes];
  for (const client of nodes.filter((node) => node.kind === "client")) {
    const existingIndex = nodes.findIndex((node) => node.parentId === client.id && node.name.trim().toLocaleLowerCase() === "client profile");
    if (existingIndex >= 0) {
      const existing = nodes[existingIndex];
      if (existing.kind !== "profile" || !existing.protected || existing.content === undefined) {
        nodes[existingIndex] = { ...existing, kind: "profile", protected: true, content: existing.content ?? "" };
        changed = true;
      }
      continue;
    }
    nodes.push(createClientProfile(client));
    changed = true;
  }
  return changed ? { ...data, nodes } : data;
}

function createClientProfile(client: FileSystemData["nodes"][number]) {
  return {
    id: crypto.randomUUID(),
    parentId: client.id,
    name: "Client Profile",
    kind: "profile" as const,
    createdAt: client.createdAt,
    updatedAt: client.updatedAt,
    tags: [],
    shared: false,
    needsAttention: false,
    trashedAt: client.trashedAt,
    content: "",
    protected: true,
  };
}

export function saveFileSystem(accountId: string, data: FileSystemData) {
  window.localStorage.setItem(accountStorageKey(storageNamespace, accountId), JSON.stringify(data));
}

export async function loadServerFileSystem(): Promise<FileSystemData> {
  const response = await fetch("/api/filesystem/snapshot", { cache: "no-store" });
  const nodes = await response.json() as Array<{
    id: string; parentId: string | null; name: string; kind: FileSystemData["nodes"][number]["kind"];
    createdAt: string; updatedAt: string; shared: boolean; needsAttention: boolean;
    trashedAt: string | null; content: string | null;
  }> | { error?: string };
  if (!response.ok || !Array.isArray(nodes)) throw new Error(!Array.isArray(nodes) && nodes.error || "Could not load the client folders.");
  return { version: 1, nodes: nodes.map((node) => ({ ...node, content: node.content ?? undefined, tags: [], protected: node.kind === "profile" })) };
}

export function mergeFileSystems(local: FileSystemData, server: FileSystemData): FileSystemData {
  const localById = new Map(local.nodes.map((node) => [node.id, node]));
  const serverIds = new Set(server.nodes.map((node) => node.id));
  const nodes: FileSystemData["nodes"] = server.nodes.map((node) => {
    const saved = localById.get(node.id);
    return { ...saved, ...node, tags: saved?.tags ?? [], protected: node.kind === "profile" };
  });
  nodes.push(...local.nodes.filter((node) => !serverIds.has(node.id)));
  return { version: 1, nodes };
}

export async function syncFileSystem(data: FileSystemData): Promise<void> {
  const response = await fetch("/api/filesystem/sync", {
    body: JSON.stringify({
      nodes: data.nodes.map((node) => ({
        id: node.id,
        parent_id: node.parentId,
        name: node.name,
        kind: node.kind,
        shared: node.shared,
        needs_attention: node.needsAttention,
        trashed_at: node.trashedAt,
        content: node.content,
      })),
    }),
    headers: { "Content-Type": "application/json" },
    method: "PUT",
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({})) as { error?: string };
    throw new Error(payload.error || "Could not synchronize the client folders.");
  }
}

function isFileSystemData(value: unknown): value is FileSystemData {
  if (!value || typeof value !== "object") return false;
  const data = value as Partial<FileSystemData>;
  return data.version === 1 && Array.isArray(data.nodes);
}
