/**
 * Browser Notification helper — thin wrapper around the Web Notification API.
 *
 * Intentionally uses the *Web Notification* API, NOT the *Web Push* API.
 * Tradeoffs:
 *  - No VAPID keys, no service worker, no HTTPS requirement (works on http://localhost).
 *  - No external services (no FCM, APNs, SendGrid, etc.).
 *  - Only delivers notifications while the browser is running — does NOT push to
 *    a phone or deliver when the browser is closed. For true mobile push, the
 *    production path is APNs/FCM (documented in ComplianceSprintPlan Sprint 6).
 *
 * Usage:
 *   import { requestNotificationPermission, notify } from '../utils/notifications';
 *
 *   // Call once when the user performs an action that could result in a
 *   // notification (clicking Connect, starting Analyze, etc.). Browsers only
 *   // prompt once; subsequent calls are no-ops.
 *   await requestNotificationPermission();
 *
 *   // Fire a notification. Silently no-ops if permission not granted or if
 *   // the tab is currently visible (configurable).
 *   notify({
 *     title: '🚨 Suspicious activity detected',
 *     body: 'Shoplifting · 87% confidence',
 *     tag: 'live-stream-alert',
 *   });
 */

export type NotificationSupport = 'unsupported' | 'default' | 'granted' | 'denied';

/**
 * Get the current notification permission state.
 * Returns 'unsupported' when the Notification API is not available
 * (e.g., insecure context or very old browsers).
 */
export function getNotificationSupport(): NotificationSupport {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return 'unsupported';
  }
  return Notification.permission as NotificationSupport;
}

/**
 * Request notification permission from the user.
 *
 * Safe to call multiple times — browsers remember the answer and will not
 * re-prompt after the first decision. Must be called in response to a user
 * gesture (click, form submit, etc.) on some browsers, so wire it to an
 * explicit action like "Connect" or "Analyze".
 */
export async function requestNotificationPermission(): Promise<NotificationSupport> {
  const current = getNotificationSupport();
  if (current === 'unsupported' || current === 'granted' || current === 'denied') {
    return current;
  }
  try {
    const result = await Notification.requestPermission();
    return result as NotificationSupport;
  } catch {
    return 'denied';
  }
}

interface NotifyOptions {
  /** Notification title (top line, bold). */
  title: string;
  /** Body text (second line). */
  body?: string;
  /** Icon URL (defaults to /favicon.svg). */
  icon?: string;
  /**
   * Notification tag — notifications with the same tag replace each other
   * instead of stacking. Useful to prevent spam from rapid events.
   */
  tag?: string;
  /**
   * When true (default), the notification is suppressed if the user is
   * currently looking at the tab. This prevents spam: if the AlertFeed is
   * already showing the event on screen, a duplicate desktop notification
   * would be noise.
   */
  skipIfVisible?: boolean;
  /**
   * Optional click handler. Defaults to focusing the window and closing
   * the notification (which is almost always what you want).
   */
  onClick?: () => void;
}

/**
 * Show a browser notification.
 *
 * Silently no-ops and returns null if:
 *  - The Notification API is not supported
 *  - The user has not granted permission (including 'default' and 'denied')
 *  - The tab is currently visible and skipIfVisible is true (default)
 *
 * Returns the Notification instance on success (useful for advanced
 * callers that want to attach additional event listeners).
 */
export function notify(options: NotifyOptions): Notification | null {
  const {
    title,
    body,
    icon = '/favicon.svg',
    tag,
    skipIfVisible = true,
    onClick,
  } = options;

  if (getNotificationSupport() !== 'granted') return null;
  if (
    skipIfVisible &&
    typeof document !== 'undefined' &&
    document.visibilityState === 'visible'
  ) {
    return null;
  }

  try {
    const n = new Notification(title, { body, icon, tag });
    n.onclick = () => {
      if (typeof window !== 'undefined') window.focus();
      if (onClick) onClick();
      n.close();
    };
    return n;
  } catch {
    // Notification constructor can throw in some edge cases (e.g., iOS Safari
    // on non-PWA contexts). Fail silently — the feature is non-critical.
    return null;
  }
}
