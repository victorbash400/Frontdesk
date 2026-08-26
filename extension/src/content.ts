type BrowserAction = {
  type: 'frontDeskBrowserAction';
  kind: 'move' | 'click' | 'type' | 'key' | 'navigate';
  label?: string;
  x?: number;
  y?: number;
};

type BrowserOverlayMessage = BrowserAction | { type: 'frontDeskBrowserOverlayHide' };

const CURSOR_SIZE = 44;
const CURSOR_HALF = 23;
let lastPosition: { x: number; y: number } | undefined;
let sequence = 0;

if (!(globalThis as typeof globalThis & { __frontDeskBrowserOverlayReady?: boolean }).__frontDeskBrowserOverlayReady) {
  (globalThis as typeof globalThis & { __frontDeskBrowserOverlayReady?: boolean }).__frontDeskBrowserOverlayReady = true;
  chrome.runtime.onMessage.addListener((message: BrowserOverlayMessage) => {
    if (message.type === 'frontDeskBrowserOverlayHide') {
      document.querySelector('[data-front-desk-overlay]')?.remove();
      return;
    }
    if (message.type === 'frontDeskBrowserAction')
      showAction(message);
  });
}

function showAction(action: BrowserAction): void {
  const overlay = ensureOverlay();
  const cursor = overlay.shadowRoot!.querySelector<HTMLElement>('[data-front-desk-cursor]')!;
  const label = overlay.shadowRoot!.querySelector<HTMLElement>('[data-front-desk-label]')!;
  const next = coordinates(action);
  const target = targetAt(next.x, next.y, action.kind);
  label.textContent = action.label || actionText(action.kind, target);
  cursor.dataset.visible = 'true';
  cursor.dataset.horizontal = next.x > window.innerWidth - 300 ? 'left' : 'right';
  cursor.dataset.vertical = next.y > window.innerHeight - 110 ? 'up' : 'down';
  cursor.style.transform = `translate3d(${next.x - CURSOR_HALF}px, ${next.y - CURSOR_HALF}px, 0)`;
  lastPosition = next;
  if (action.kind === 'click') {
    const ripple = document.createElement('span');
    ripple.className = 'front-desk-cursor-click';
    ripple.dataset.sequence = String(++sequence);
    cursor.appendChild(ripple);
    window.setTimeout(() => ripple.remove(), 1040);
  }
}

function coordinates(action: BrowserAction): { x: number; y: number } {
  if (Number.isFinite(action.x) && Number.isFinite(action.y))
    return { x: action.x as number, y: action.y as number };
  if (lastPosition)
    return lastPosition;
  const active = document.activeElement instanceof HTMLElement ? document.activeElement.getBoundingClientRect() : undefined;
  if (active?.width && active.height)
    return { x: active.left + active.width / 2, y: active.top + active.height / 2 };
  return { x: window.innerWidth / 2, y: Math.min(120, window.innerHeight / 3) };
}

function targetAt(x: number, y: number, kind: BrowserAction['kind']): Element | null {
  if (kind === 'type' || kind === 'key')
    return document.activeElement;
  return document.elementFromPoint(x, y);
}

function actionText(kind: BrowserAction['kind'], target: Element | null): string {
  const name = elementName(target);
  if (kind === 'click') return name ? `Clicking ${name}` : 'Clicking';
  if (kind === 'type') return name ? `Typing in ${name}` : 'Typing';
  if (kind === 'key') return name ? `Using keyboard in ${name}` : 'Using keyboard';
  if (kind === 'navigate') return 'Opening page';
  return name ? `Moving to ${name}` : 'Moving pointer';
}

function elementName(target: Element | null): string {
  if (!target || target.closest('[data-front-desk-overlay]'))
    return '';
  const labelledBy = target.getAttribute('aria-labelledby');
  const labelledText = labelledBy
    ?.split(/\s+/)
    .map(id => document.getElementById(id)?.textContent?.trim())
    .filter(Boolean)
    .join(' ');
  const candidate = target.getAttribute('aria-label')
    || labelledText
    || target.getAttribute('placeholder')
    || (target instanceof HTMLInputElement ? target.name : '')
    || target.textContent?.trim()
    || target.getAttribute('title')
    || '';
  return candidate.replace(/\s+/g, ' ').slice(0, 54);
}

function ensureOverlay(): HTMLElement {
  const existing = document.querySelector<HTMLElement>('[data-front-desk-overlay]');
  if (existing)
    return existing;
  const host = document.createElement('div');
  host.dataset.frontDeskOverlay = 'true';
  host.style.cssText = 'all:initial;position:fixed;inset:0;z-index:2147483647;pointer-events:none;overflow:hidden;contain:strict;';
  const shadow = host.attachShadow({ mode: 'open' });
  const style = document.createElement('style');
  style.textContent = `
    *{box-sizing:border-box}
    .cursor{position:absolute;top:0;left:0;width:46px;height:46px;opacity:0;will-change:transform;transition:transform 650ms cubic-bezier(.34,.04,.16,1),opacity 140ms ease;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",sans-serif}
    .cursor[data-visible="true"]{opacity:1}
    .icon{position:relative;z-index:2;display:block;width:${CURSOR_SIZE}px;height:${CURSOR_SIZE}px;filter:drop-shadow(0 3px 4px rgb(0 0 0 / 24%))}
    .icon svg{display:block;width:100%;height:100%;overflow:visible}
    .label{position:absolute;top:39px;left:25px;width:max-content;max-width:260px;overflow:hidden;padding:8px 10px;border:1px solid rgb(32 32 30 / 10%);border-radius:10px;background:rgb(248 248 246 / 94%);box-shadow:0 8px 24px rgb(0 0 0 / 12%);backdrop-filter:blur(14px);color:#242422;font-size:12px;font-weight:590;line-height:1.3;text-overflow:ellipsis;white-space:nowrap}
    .cursor[data-horizontal="left"] .label{right:25px;left:auto}.cursor[data-vertical="up"] .label{top:auto;bottom:39px}
    .front-desk-cursor-click{position:absolute;top:15px;left:15px;z-index:1;width:16px;height:16px;border:1px solid rgb(45 45 43 / 40%);border-radius:50%;animation:click 520ms 480ms ease-out both}
    @keyframes click{from{opacity:.8;transform:scale(.3)}to{opacity:0;transform:scale(1.8)}}
    @media(prefers-reduced-motion:reduce){.cursor{transition:opacity 140ms ease}.front-desk-cursor-click{animation:none}}
  `;
  const cursor = document.createElement('div');
  cursor.className = 'cursor';
  cursor.dataset.frontDeskCursor = 'true';
  cursor.innerHTML = '<span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M13.4049 17.3737C12.1169 20.1754 7.94756 19.4443 7.6896 16.3716L7.10914 9.45749C6.89678 6.92797 9.72627 5.29437 11.8107 6.74304L17.5083 10.7028C20.0404 12.4626 18.5888 16.4388 15.5185 16.1534L14.7348 16.0805C14.3122 16.0412 13.9109 16.273 13.7336 16.6585L13.4049 17.3737Z" fill="#2d2d2b" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/></svg></span><span class="label" data-front-desk-label></span>';
  shadow.append(style, cursor);
  (document.documentElement || document).appendChild(host);
  return host;
}
