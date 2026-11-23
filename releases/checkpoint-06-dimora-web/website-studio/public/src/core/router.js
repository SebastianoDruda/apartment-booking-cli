/**
 * Hash-based routing (#/path?query). Works on any static host without
 * server-side rewrites. Hashes that do not start with "#/" are ignored.
 */

export function parseHash(hash = globalThis.location?.hash ?? '') {
  const value = hash.startsWith('#/') ? hash.slice(1) : '/';
  const [rawPath, rawQuery = ''] = value.split('?');
  const path = rawPath.replace(/\/+$/, '') || '/';
  return { path, query: Object.fromEntries(new URLSearchParams(rawQuery)) };
}

export function buildHash(path, query = {}) {
  const params = new URLSearchParams(
    Object.entries(query).filter(([, value]) => value !== '' && value !== null && value !== undefined),
  ).toString();
  return `#${path}${params ? `?${params}` : ''}`;
}

/** Update the address bar without re-rendering (keeps filters shareable). */
export function replaceQuery(path, query) {
  history.replaceState(null, '', buildHash(path, query));
}
