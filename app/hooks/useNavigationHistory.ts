"use client";

import { useCallback, useState } from "react";

import type { Destination } from "../types/filesystem";

const initialDestination: Destination = { type: "location", location: "clients" };

export function useNavigationHistory() {
  const [entries, setEntries] = useState<Destination[]>([initialDestination]);
  const [index, setIndex] = useState(0);
  const destination = entries[index];

  const navigate = useCallback((next: Destination) => {
    setEntries((current) => [...current.slice(0, index + 1), next]);
    setIndex((current) => current + 1);
  }, [index]);

  const back = useCallback(() => setIndex((current) => Math.max(0, current - 1)), []);
  const forward = useCallback(() => setIndex((current) => Math.min(entries.length - 1, current + 1)), [entries.length]);

  return {
    destination,
    navigate,
    back,
    forward,
    canGoBack: index > 0,
    canGoForward: index < entries.length - 1,
  };
}
