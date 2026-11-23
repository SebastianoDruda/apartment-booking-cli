/**
 * Role-based demo sessions.
 *
 * The booking API has no authentication, so Dimora does not ask for credentials.
 * A guest enters with their own name, exactly as the CLI asks "Your name" when
 * booking: it is the booker name on new bookings and how "My trips" finds them.
 * The host opens the host's demo profile. Real accounts need server-side
 * authentication first (see website-studio/README.md).
 */
import { MAX_NAME_LENGTH, ROLES, SESSION_TTL_MS, STORAGE_KEYS } from '../config.js';
import { storage as defaultStorage } from '../core/storage.js';

export const PERSONAS = {
  host: { name: 'Sebastiano Druda' },
};

/** Trim and collapse whitespace; the API stores booker names trimmed as well. */
export function cleanName(value) {
  return String(value ?? '').trim().replace(/\s+/g, ' ').slice(0, MAX_NAME_LENGTH);
}

export function createAuthService({ storage = defaultStorage, now = () => Date.now() } = {}) {
  return {
    enter(role, name = '') {
      if (!ROLES.includes(role)) throw new Error(`Unknown role: ${role}`);
      let sessionName = PERSONAS.host.name;
      if (role === 'guest') {
        sessionName = cleanName(name);
        if (!sessionName) throw new Error('A guest needs a name.');
        storage.write(STORAGE_KEYS.guestName, sessionName);
      }
      const session = { role, name: sessionName, expiresAt: now() + SESSION_TTL_MS };
      storage.write(STORAGE_KEYS.session, session);
      return session;
    },

    /** The name the last guest entered with, to prefill the entry form. */
    lastGuestName() {
      const name = storage.read(STORAGE_KEYS.guestName, '');
      return typeof name === 'string' ? cleanName(name) : '';
    },

    getSession() {
      const session = storage.read(STORAGE_KEYS.session, null);
      const valid = session && typeof session === 'object' && ROLES.includes(session.role)
        && typeof session.name === 'string' && session.name.trim() !== '' && session.expiresAt > now();
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
