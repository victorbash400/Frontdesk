export const AGENT_MICROPHONE_NAME = 'Agent Mike';
export const AGENT_EARS_NAME = 'Agent Ears';

export function isAudioDeviceLabel(label: string, name: string): boolean {
  return label.replace(/\s+\(Virtual\)$/i, '') === name;
}

export function agentEarsConstraints(deviceId: string): MediaTrackConstraints {
  return {
    deviceId: { exact: deviceId },
    channelCount: 1,
    echoCancellation: false,
    noiseSuppression: false,
    autoGainControl: false,
  };
}
