export type MailboxState = {
  connected: boolean;
  provider: "titan";
  email: string | null;
  state: "connected" | "disconnected" | "failed";
  failure: string | null;
  lastUid: number;
};
