export const cloudApiOrigin = import.meta.env.VITE_FRONT_DESK_API_ORIGIN || '';
export const cloudAppOrigin = import.meta.env.VITE_FRONT_DESK_APP_ORIGIN || 'http://localhost:3000';

const loopbackHosts = new Set(['localhost', '127.0.0.1', '[::1]']);

export function isCloudRelay(url: string): boolean {
  if (!cloudApiOrigin) return false;
  try {
    const parsed = new URL(url);
    const api = new URL(cloudApiOrigin);
    // A loopback API origin only ever comes from a local development build, where the
    // backend serves plain HTTP and the relay is plain ws on that same loopback host.
    // Every remote origin keeps the transport-security requirement unchanged.
    const transport = loopbackHosts.has(api.hostname)
      ? parsed.protocol === 'ws:' && api.protocol === 'http:' && loopbackHosts.has(parsed.hostname)
      : parsed.protocol === 'wss:' && api.protocol === 'https:';
    return transport
      && parsed.host === api.host && /^\/api\/browser\/relay\/[A-Za-z0-9_-]{43}$/.test(parsed.pathname)
      && !parsed.search && !parsed.hash && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}
