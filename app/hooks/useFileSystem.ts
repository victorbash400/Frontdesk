"use client";

import { useCallback, useEffect, useState } from "react";

import { loadFileSystem, saveFileSystem } from "../lib/fileSystemStorage";
import { hasSiblingName } from "../lib/fileSystemNames";
import type { FileSystemData, FileSystemNode, NodeKind, TagName } from "../types/filesystem";

const initialData: FileSystemData = { version: 1, nodes: [] };

export function useFileSystem() {
  const [data, setData] = useState(initialData);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string>();

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      try {
        setData(loadFileSystem());
      } catch (reason) {
        setError(messageFrom(reason, "Could not load the filesystem."));
      } finally {
        setLoaded(true);
      }
    });

    return () => window.cancelAnimationFrame(frame);
  }, []);

  const commit = useCallback((update: (current: FileSystemData) => FileSystemData) => {
    setData((current) => {
      const next = update(current);
      try {
        saveFileSystem(next);
        setError(undefined);
        return next;
      } catch (reason) {
        setError(messageFrom(reason, "Could not save the filesystem."));
        return current;
      }
    });
  }, []);

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
    commit((current) => ({ ...current, nodes: [...current.nodes, node] }));
    return node;
  }, [commit, data.nodes]);

  const updateNode = useCallback((id: string, update: Partial<Pick<FileSystemNode, "name" | "parentId" | "shared" | "needsAttention" | "trashedAt">>) => {
    const currentNode = data.nodes.find((node) => node.id === id);
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
  }, [commit]);

  return { data, loaded, error, createNode, updateNode, toggleTag, setTrashed };
}

function messageFrom(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback;
}
