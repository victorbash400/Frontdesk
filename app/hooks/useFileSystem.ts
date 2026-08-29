"use client";

import { useCallback, useEffect, useState } from "react";

import { loadFileSystem, loadServerFileSystem, mergeFileSystems, saveFileSystem, syncFileSystem } from "../lib/fileSystemStorage";
import { hasSiblingName } from "../lib/fileSystemNames";
import type { FileSystemData, FileSystemNode, NodeKind, TagName } from "../types/filesystem";

const initialData: FileSystemData = { version: 1, nodes: [] };

export function useFileSystem(accountId: string) {
  const [data, setData] = useState(initialData);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        const stored = loadFileSystem(accountId);
        setData(stored);
        void syncFileSystem(stored)
          .then(loadServerFileSystem)
          .then((server) => {
            const merged = mergeFileSystems(stored, server);
            saveFileSystem(accountId, merged);
            setData(merged);
          })
          .catch((reason) => setError(messageFrom(reason, "Could not synchronize the client folders.")));
      } catch (reason) {
        setError(messageFrom(reason, "Could not load the filesystem."));
      } finally {
        setLoaded(true);
      }
    });
    const events = new EventSource("/api/events/stream");
    events.onmessage = (message) => {
      const event = JSON.parse(message.data) as { type?: string };
      if (event.type !== "mailbox_changed") return;
      void loadServerFileSystem().then((server) => setData((current) => {
        const merged = mergeFileSystems(current, server);
        saveFileSystem(accountId, merged);
        return merged;
      })).catch((reason) => setError(messageFrom(reason, "Could not refresh the client folders.")));
    };

    return () => { window.cancelAnimationFrame(frame); events.close(); };
  }, [accountId]);

  const commit = useCallback((update: (current: FileSystemData) => FileSystemData) => {
    setData((current) => {
      const next = update(current);
      try {
        saveFileSystem(accountId, next);
        void syncFileSystem(next).catch((reason) => setError(messageFrom(reason, "Could not synchronize the client folders.")));
        setError(undefined);
        return next;
      } catch (reason) {
        setError(messageFrom(reason, "Could not save the filesystem."));
        return current;
      }
    });
  }, [accountId]);

  const createNode = useCallback((name: string, kind: NodeKind, parentId: string | null) => {
    if (hasSiblingName(data.nodes, name, parentId)) throw new Error(`“${name}” already exists in this folder.`);
    const timestamp = new Date().toISOString();
    const node: FileSystemNode = {
      id: crypto.randomUUID(),
      parentId,
      name,
      kind,
      createdAt: timestamp,
      updatedAt: timestamp,
      tags: [],
      shared: false,
      needsAttention: false,
      trashedAt: null,
    };
    const additions = kind === "client" ? [node, createClientProfile(node)] : [node];
    commit((current) => ({ ...current, nodes: [...current.nodes, ...additions] }));
    return node;
  }, [commit, data.nodes]);

  const updateNode = useCallback((id: string, update: Partial<Pick<FileSystemNode, "name" | "parentId" | "shared" | "needsAttention" | "trashedAt" | "content">>) => {
    const currentNode = data.nodes.find((node) => node.id === id);
    if (currentNode?.protected && (update.name !== undefined || update.parentId !== undefined || update.trashedAt !== undefined)) throw new Error("Client Profile cannot be renamed, moved, or deleted.");
    const parentId = update.parentId === undefined ? currentNode?.parentId : update.parentId;
    if (update.name && currentNode && parentId !== undefined && hasSiblingName(data.nodes, update.name, parentId, id)) {
      throw new Error(`“${update.name}” already exists in this folder.`);
    }
    commit((current) => ({
      ...current,
      nodes: current.nodes.map((node) => node.id === id ? { ...node, ...update, updatedAt: new Date().toISOString() } : node),
    }));
  }, [commit, data.nodes]);

  const toggleTag = useCallback((id: string, tag: TagName) => {
    commit((current) => ({
      ...current,
      nodes: current.nodes.map((node) => node.id === id
        ? { ...node, tags: node.tags.includes(tag) ? node.tags.filter((value) => value !== tag) : [...node.tags, tag], updatedAt: new Date().toISOString() }
        : node),
    }));
  }, [commit]);

  const setTrashed = useCallback((id: string, trashed: boolean) => {
    if (data.nodes.find((node) => node.id === id)?.protected) throw new Error("Client Profile cannot be deleted.");
    commit((current) => {
      const affected = new Set([id]);
      let changed = true;
      while (changed) {
        changed = false;
        for (const node of current.nodes) {
          if (node.parentId && affected.has(node.parentId) && !affected.has(node.id)) {
            affected.add(node.id);
            changed = true;
          }
        }
      }
      const timestamp = new Date().toISOString();
      return {
        ...current,
        nodes: current.nodes.map((node) => affected.has(node.id) ? { ...node, trashedAt: trashed ? timestamp : null, updatedAt: timestamp } : node),
      };
    });
  }, [commit, data.nodes]);

  return { data, loaded, error, createNode, updateNode, toggleTag, setTrashed };
}

function createClientProfile(client: FileSystemNode): FileSystemNode {
  return {
    id: crypto.randomUUID(),
    parentId: client.id,
    name: "Client Profile",
    kind: "profile",
    createdAt: client.createdAt,
    updatedAt: client.updatedAt,
    tags: [],
    shared: false,
    needsAttention: false,
    trashedAt: null,
    content: "",
    protected: true,
  };
}

function messageFrom(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
