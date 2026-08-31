export type AudioFrame = {
  numberOfChannels: number;
  numberOfFrames: number;
  sampleRate: number;
  copyTo(destination: Float32Array, options: { planeIndex: number; format: 'f32-planar' }): void;
  close(): void;
};

export function downmixAndResample(frame: AudioFrame, targetRate: number): Float32Array {
  const channels = Array.from({ length: frame.numberOfChannels }, (_, planeIndex) => {
    const samples = new Float32Array(frame.numberOfFrames);
    frame.copyTo(samples, { planeIndex, format: 'f32-planar' });
    return samples;
  });
  const outputLength = Math.max(1, Math.round(frame.numberOfFrames * targetRate / frame.sampleRate));
  const output = new Float32Array(outputLength);
  for (let outputIndex = 0; outputIndex < outputLength; outputIndex++) {
    const sourceIndex = Math.min(frame.numberOfFrames - 1, Math.floor(outputIndex * frame.sampleRate / targetRate));
    for (const channel of channels)
      output[outputIndex] += channel[sourceIndex] / channels.length;
  }
  return output;
}

export function resampleMono(samples: Float32Array, sourceRate: number, targetRate: number): Float32Array {
  const outputLength = Math.max(1, Math.round(samples.length * targetRate / sourceRate));
  const output = new Float32Array(outputLength);
  for (let outputIndex = 0; outputIndex < outputLength; outputIndex++) {
    const sourcePosition = outputIndex * sourceRate / targetRate;
    const leftIndex = Math.min(samples.length - 1, Math.floor(sourcePosition));
    const rightIndex = Math.min(samples.length - 1, leftIndex + 1);
    const fraction = sourcePosition - leftIndex;
    output[outputIndex] = samples[leftIndex] * (1 - fraction) + samples[rightIndex] * fraction;
  }
  return output;
}

export function normalizePcmLevel(samples: Int16Array, targetRms = 0.05, maximumGain = 8): Int16Array {
  let energy = 0;
  for (const sample of samples)
    energy += (sample / 0x8000) ** 2;
  const rms = Math.sqrt(energy / Math.max(1, samples.length));
  const gain = rms > 0 ? Math.min(maximumGain, Math.max(1, targetRms / rms)) : 1;
  const output = new Int16Array(samples.length);
  for (let index = 0; index < samples.length; index++) {
    const amplified = Math.round(samples[index] * gain);
    output[index] = Math.max(-0x8000, Math.min(0x7fff, amplified));
  }
  return output;
}

export function pcmPacket(channel: number, samples: Float32Array): Uint8Array {
  const packet = new Uint8Array(1 + samples.length * 2);
  packet[0] = channel;
  const view = new DataView(packet.buffer);
  for (let index = 0; index < samples.length; index++)
    view.setInt16(1 + index * 2, Math.max(-1, Math.min(1, samples[index])) * 0x7fff, true);
  return packet;
}
