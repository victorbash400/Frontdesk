import { describe, expect, it } from 'vitest';

import { downmixAndResample, pcmPacket, resampleMono, type AudioFrame } from './audioPcm';

describe('meeting PCM conversion', () => {
  it('resamples Web Audio mono buffers', () => {
    expect([...resampleMono(new Float32Array([0, 1, 0, -1]), 4, 8)]).toEqual([0, 0.5, 1, 0.5, 0, -0.5, -1, -1]);
  });

  it('downmixes stereo audio and resamples it to 16 kHz', () => {
    const planes = [new Float32Array([1, 0, -1]), new Float32Array([0, 0, 0])];
    const frame: AudioFrame = {
      numberOfChannels: 2,
      numberOfFrames: 3,
      sampleRate: 48_000,
      copyTo(destination, { planeIndex }) {
        destination.set(planes[planeIndex]);
      },
      close() {},
    };

    expect([...downmixAndResample(frame, 16_000)]).toEqual([0.5]);
  });

  it('encodes signed little-endian PCM with its channel byte', () => {
    const packet = pcmPacket(1, new Float32Array([-1, 0, 1]));
    const view = new DataView(packet.buffer);

    expect(packet[0]).toBe(1);
    expect(view.getInt16(1, true)).toBe(-32767);
    expect(view.getInt16(3, true)).toBe(0);
    expect(view.getInt16(5, true)).toBe(32767);
  });
});
