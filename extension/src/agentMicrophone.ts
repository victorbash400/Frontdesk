import { AGENT_MICROPHONE_NAME, isAudioDeviceLabel } from './agentAudioDevices';

export { AGENT_MICROPHONE_NAME };

export function isAgentMicrophoneLabel(label: string): boolean {
  return isAudioDeviceLabel(label, AGENT_MICROPHONE_NAME);
}
