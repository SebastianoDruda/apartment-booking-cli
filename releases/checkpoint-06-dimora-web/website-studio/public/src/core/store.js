/** Minimal observable store for cross-cutting UI state (locale, session). */
export function createStore(initial) {
  let state = { ...initial };
  const listeners = new Set();

  return {
    get: () => state,
    set(patch) {
      const previous = state;
      state = { ...state, ...patch };
      listeners.forEach((listener) => listener(state, previous));
    },
    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}
