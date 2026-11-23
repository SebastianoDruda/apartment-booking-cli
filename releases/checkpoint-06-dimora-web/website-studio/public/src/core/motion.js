/** Motion helpers. Every effect is skipped when the user prefers reduced motion. */

export const prefersReducedMotion = () =>
  globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;

let revealObserver = null;

export function observeReveals(root) {
  const items = [...root.querySelectorAll('.reveal:not(.is-visible)')];
  if (prefersReducedMotion() || !('IntersectionObserver' in globalThis)) {
    items.forEach((item) => item.classList.add('is-visible'));
    return;
  }
  revealObserver ??= new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        revealObserver.unobserve(entry.target);
      }
    });
  }, { rootMargin: '0px 0px -6% 0px', threshold: 0.06 });

  items.forEach((item) => {
    const siblings = [...(item.parentElement?.children ?? [])].filter((node) => node.classList.contains('reveal'));
    item.style.setProperty('--d', String(Math.min(siblings.indexOf(item), 8)));
    revealObserver.observe(item);
  });
}

export function countUp(element, target, format = String, duration = 1100) {
  if (prefersReducedMotion()) {
    element.textContent = format(target);
    return;
  }
  const start = performance.now();
  const tick = (now) => {
    const progress = Math.min(1, (now - start) / duration);
    const eased = 1 - (1 - progress) ** 4;
    const value = target * eased;
    element.textContent = format(progress === 1 ? target : Number.isInteger(target) ? Math.round(value) : value);
    if (progress < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

/** Cursor-following glow for `.spotlight` cards. */
export function initPointerEffects() {
  document.addEventListener('pointermove', (event) => {
    const card = event.target instanceof Element ? event.target.closest('.spotlight') : null;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    card.style.setProperty('--mx', `${event.clientX - rect.left}px`);
    card.style.setProperty('--my', `${event.clientY - rect.top}px`);
  }, { passive: true });
}

export function withViewTransition(update) {
  if (typeof document.startViewTransition !== 'function' || prefersReducedMotion()) {
    update();
    return;
  }
  document.startViewTransition(update);
}
