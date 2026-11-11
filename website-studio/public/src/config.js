/** Application-wide constants. */

export const API_BASE =
  globalThis.document?.querySelector('meta[name="dimora-api-base"]')?.getAttribute('content') || '/api';

export const STORAGE_KEYS = {
  locale: 'dimora.locale',
  theme: 'dimora.theme',
  accounts: 'dimora.accounts.v1',
  session: 'dimora.session.v1',
};

export const ROLES = ['guest', 'host'];

export const HOME = {
  guest: '/guest/explore',
  host: '/host/overview',
};

export const NAV = {
  guest: [
    { path: '/guest/explore', label: 'shell.nav.explore', icon: 'compass' },
    { path: '/guest/trips', label: 'shell.nav.trips', icon: 'suitcase' },
  ],
  host: [
    { path: '/host/overview', label: 'shell.nav.overview', icon: 'grid' },
    { path: '/host/listings', label: 'shell.nav.listings', icon: 'home' },
    { path: '/host/reservations', label: 'shell.nav.reservations', icon: 'calendar' },
  ],
};

export const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;
export const MAX_GUESTS = 30;
