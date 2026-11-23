/**
 * HTTP client for the Apartment Booking REST API.
 * Successful responses are unwrapped from `{ data }`; failures become ApiError
 * with the API's machine-readable `error.code`.
 *
 * Read-your-writes with the event-driven edition (microservices/): a write
 * answers with an `X-Consistency-Token`; the client sends pending tokens back
 * in `X-Wait-For` on its next reads, and the query service waits until its read
 * model includes them (`X-Consistency: fresh`). The original API sends no
 * tokens, so nothing changes there.
 */
import { API_BASE } from '../config.js';

const TOKEN_HEADER = 'X-Consistency-Token';
const WAIT_HEADER = 'X-Wait-For';
const STATUS_HEADER = 'X-Consistency';
const MAX_PENDING_TOKENS = 10;

export class ApiError extends Error {
  constructor({ status, code, message }) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function createApiClient({ baseUrl = API_BASE, fetchImpl = (...args) => globalThis.fetch(...args) } = {}) {
  let pendingTokens = [];

  async function request(method, path, { query, body, signal } = {}) {
    const search = query ? `?${new URLSearchParams(query)}` : '';
    const init = { method, signal, headers: { Accept: 'application/json' } };
    if (body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    const sentTokens = method === 'GET' ? [...pendingTokens] : [];
    if (sentTokens.length) init.headers[WAIT_HEADER] = sentTokens.join(', ');

    let response;
    try {
      response = await fetchImpl(`${baseUrl}${path}${search}`, init);
    } catch (error) {
      if (error?.name === 'AbortError') throw error;
      throw new ApiError({ status: 0, code: 'network', message: 'Network request failed.' });
    }

    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }

    if (!response.ok) {
      throw new ApiError({
        status: response.status,
        code: payload?.error?.code ?? `http_${response.status}`,
        message: payload?.error?.message ?? response.statusText,
      });
    }
    const token = response.headers?.get?.(TOKEN_HEADER);
    if (token && method !== 'GET') {
      pendingTokens = [...pendingTokens, token].slice(-MAX_PENDING_TOKENS);
    } else if (sentTokens.length && response.headers?.get?.(STATUS_HEADER)) {
      pendingTokens = pendingTokens.filter((pending) => !sentTokens.includes(pending));
    }
    return payload?.data;
  }

  return {
    get: (path, options) => request('GET', path, options),
    post: (path, body, options) => request('POST', path, { ...options, body }),
    patch: (path, body, options) => request('PATCH', path, { ...options, body }),
    delete: (path, options) => request('DELETE', path, options),
  };
}

export const api = createApiClient();
