import { describe, expect, it, vi } from 'vitest';

describe('cloud relay URL validation', () => {
  it('accepts only the configured HTTPS backend and exact ticket path', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_FRONT_DESK_API_ORIGIN', 'https://api.frontdesk.test');
    const { isCloudRelay } = await import('./cloudConfig');
    const path = `/api/browser/relay/${'x'.repeat(43)}`;
    expect(isCloudRelay(`wss://api.frontdesk.test${path}`)).toBe(true);
    expect(isCloudRelay(`ws://api.frontdesk.test${path}`)).toBe(false);
    expect(isCloudRelay(`wss://attacker.test${path}`)).toBe(false);
    expect(isCloudRelay(`wss://api.frontdesk.test${path}?extra=1`)).toBe(false);
    vi.unstubAllEnvs();
  });

  it('accepts a plain ws relay only for a loopback development origin', async () => {
    vi.resetModules();
    vi.stubEnv('VITE_FRONT_DESK_API_ORIGIN', 'http://127.0.0.1:8000');
    const { isCloudRelay } = await import('./cloudConfig');
    const path = `/api/browser/relay/${'x'.repeat(43)}`;
    expect(isCloudRelay(`ws://127.0.0.1:8000${path}`)).toBe(true);
    expect(isCloudRelay(`ws://evil.test${path}`)).toBe(false);
    expect(isCloudRelay(`ws://127.0.0.1:8000${path}?extra=1`)).toBe(false);
    vi.unstubAllEnvs();
  });
});
