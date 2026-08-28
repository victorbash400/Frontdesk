import { describe, expect, it } from 'vitest';
import { isAgentMicrophoneLabel } from './agentMicrophone';

describe('isAgentMicrophoneLabel', () => {
  it('accepts the Core Audio device name', () => {
    expect(isAgentMicrophoneLabel('Agent Mike')).toBe(true);
  });

  it('accepts Chrome virtual-device decoration', () => {
    expect(isAgentMicrophoneLabel('Agent Mike (Virtual)')).toBe(true);
  });

  it('does not accept physical or unrelated microphones', () => {
    expect(isAgentMicrophoneLabel('MacBook Air Microphone (Built-in)')).toBe(false);
    expect(isAgentMicrophoneLabel('BlackHole 2ch (Virtual)')).toBe(false);
  });
});
