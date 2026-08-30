export const cloudApiOrigin = import.meta.env.VITE_FRONT_DESK_API_ORIGIN || '';
export const cloudAppOrigin = import.meta.env.VITE_FRONT_DESK_APP_ORIGIN || 'http://localhost:3000';

export function isCloudRelay(url: string): boolean {
  if (!cloudApiOrigin) return false;
  try {
    const parsed = new URL(url);
    const api = new URL(cloudApiOrigin);
    return parsed.protocol === 'wss:' && api.protocol === 'https:'
      && parsed.host === api.host && /^\/api\/browser\/relay\/[A-Za-z0-9_-]{43}$/.test(parsed.pathname)
      && !parsed.search && !parsed.hash && !parsed.username && !parsed.password;
  } catch {
    return false;
  }
}
