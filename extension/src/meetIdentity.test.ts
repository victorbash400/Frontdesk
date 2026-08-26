import { describe, expect, it } from 'vitest';
import { relayDecision, validRelayIdentity } from './meetIdentity';

const current = { meetingId: 'meeting-1', runtimeId: 'runtime-1', bridgeId: 'bridge-1', tabId: 10 };

describe('Meet relay identity', () => {
  it('reuses only the exact runtime, bridge, and tab', () => {
    expect(relayDecision(current, { ...current })).toBe('same-tab');
  });

  it('rejects another tab for the same runtime', () => {
    expect(relayDecision(current, { ...current, tabId: 11 })).toBe('reject-duplicate-tab');
    expect(relayDecision(current, { ...current, bridgeId: 'bridge-2' })).toBe('reject-duplicate-tab');
  });

  it('replaces the old tab only for a new runtime', () => {
    expect(relayDecision(current, { ...current, runtimeId: 'runtime-2', bridgeId: 'bridge-2', tabId: 11 })).toBe('replace-runtime');
  });

  it('rejects incomplete identities', () => {
    expect(validRelayIdentity({ ...current })).toBe(true);
    expect(validRelayIdentity({ ...current, runtimeId: '' })).toBe(false);
    expect(validRelayIdentity({ ...current, tabId: undefined })).toBe(false);
  });
});
