export function accountStorageKey(namespace: string, accountId: string) {
  if (!accountId.trim()) throw new Error("An authenticated account is required.");
  return `${namespace}:${accountId}`;
}
