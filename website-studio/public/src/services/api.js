/**
 * HTTP client for the Apartment Booking REST API.
 * Successful responses are unwrapped from `{ data }`; failures become ApiError
 * with the API's machine-readable `error.code`.
 */
import { API_BASE } from '../config.js';

export class ApiError extends Error {
  constructor({ status, code, message }) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function createApiClient({ baseUrl = API_BASE, fetchImpl = (...args) => globalThis.fetch(...args) } = {}) {
  async function request(method, path, { query, body, signal } = {}) {
    const search = query ? `?${new URLSearchParams(query)}` : '';
    const init = { method, signal, headers: { Accept: 'application/json' } };
    if (body !== undefined) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }

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
