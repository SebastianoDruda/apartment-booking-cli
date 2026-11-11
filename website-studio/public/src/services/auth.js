/**
 * Role-based demo sessions.
 *
 * The booking API has no authentication, so Dimora does not ask for credentials:
 * choosing a role opens that role's demo profile. The guest profile's name is the
 * booker name used on bookings, which is how "My trips" finds them. Real accounts
 * need server-side authentication first (see website-studio/README.md).
 */
import { ROLES, SESSION_TTL_MS, STORAGE_KEYS } from '../config.js';
import { storage as defaultStorage } from '../core/storage.js';

export const PERSONAS = {
  guest: { name: 'Tom Springer' },
  host: { name: 'Sebastiano Druda' },
};

export function createAuthService({ storage = defaultStorage, now = () => Date.now() } = {}) {
  return {
    enter(role) {
      if (!ROLES.includes(role)) throw new Error(`Unknown role: ${role}`);
      const session = { role, name: PERSONAS[role].name, expiresAt: now() + SESSION_TTL_MS };
      storage.write(STORAGE_KEYS.session, session);
      return session;
    },

    getSession() {
      const session = storage.read(STORAGE_KEYS.session, null);
      const valid = session && typeof session === 'object' && ROLES.includes(session.role)
        && typeof session.name === 'string' && session.expiresAt > now();
      if (!valid) {
        if (session) storage.remove(STORAGE_KEYS.session);
        return null;
      }
      return session;
    },

    signOut() {
      storage.remove(STORAGE_KEYS.session);
    },
  };
}

export const auth = createAuthService();
