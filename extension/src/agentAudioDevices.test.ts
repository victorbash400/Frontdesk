import { describe, expect, it } from 'vitest';

import { agentEarsConstraints, isAudioDeviceLabel } from './agentAudioDevices';


describe('Agent Ears', () => {
  it('matches Chrome virtual-device decoration', () => {
    expect(isAudioDeviceLabel('Agent Ears (Virtual)', 'Agent Ears')).toBe(true);
  });

  it('captures loopback audio without voice processing', () => {
    expect(agentEarsConstraints('ears-device')).toEqual({
      deviceId: { exact: 'ears-device' },
      channelCount: 1,
      echoCancellation: false,
      noiseSuppression: false,
      autoGainControl: false,
    });
  });
});
