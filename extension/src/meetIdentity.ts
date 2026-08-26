export type MeetRelayIdentity = {
  meetingId: string;
  runtimeId: string;
  bridgeId: string;
  tabId: number;
};

export type RelayDecision = 'same-tab' | 'reject-duplicate-tab' | 'replace-runtime';

export function relayDecision(current: MeetRelayIdentity, incoming: MeetRelayIdentity): RelayDecision {
  if (current.runtimeId !== incoming.runtimeId)
    return 'replace-runtime';
  if (current.bridgeId === incoming.bridgeId && current.tabId === incoming.tabId)
    return 'same-tab';
  return 'reject-duplicate-tab';
}

export function validRelayIdentity(value: Partial<MeetRelayIdentity>): value is MeetRelayIdentity {
  return Boolean(value.meetingId && value.runtimeId && value.bridgeId && Number.isInteger(value.tabId));
}
