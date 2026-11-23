/**
 * JSON storage wrapper. Browser storage can be missing or throw (private mode,
 * blocked site data), so every access is guarded and falls back gracefully.
 */

function defaultBackend() {
  try {
    return globalThis.localStorage ?? null;
  } catch {
    return null;
  }
}

export function createStorage(backend = defaultBackend()) {
  return {
    read(key, fallback = null) {
      try {
        const value = backend?.getItem(key);
        return value === null || value === undefined ? fallback : JSON.parse(value);
      } catch {
        return fallback;
      }
    },
    write(key, value) {
      try {
        backend?.setItem(key, JSON.stringify(value));
        return Boolean(backend);
      } catch {
        return false;
      }
    },
    remove(key) {
      try {
        backend?.removeItem(key);
      } catch {
        /* storage unavailable: nothing to remove */
      }
    },
  };
}

/** In-memory backend with the Web Storage interface, used by tests. */
export function memoryBackend() {
  const data = new Map();
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: (key) => data.delete(key),
  };
}

export const storage = createStorage();
