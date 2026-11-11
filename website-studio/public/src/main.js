/**
 * Composition root: wires state, routing, guards and global interactions.
 *
 * Layers (each depends only on the ones below it):
 *   views/      screens, one module per route
 *   ui/         reusable components, chrome, dialogs, toasts
 *   services/   API client, booking domain gateway, local accounts
 *   core/       html escaping, i18n, formatting, routing, motion, storage
 */
import { HOME, STORAGE_KEYS } from './config.js';
import { render } from './core/html.js';
import { detectLocale, getLocale, setLocale, t } from './core/i18n.js';
import { initPointerEffects, observeReveals, prefersReducedMotion, withViewTransition } from './core/motion.js';
import { parseHash } from './core/router.js';
import { storage } from './core/storage.js';
import { createStore } from './core/store.js';
import { notFoundRoute, routes } from './routes.js';
import { auth } from './services/auth.js';
import { appShell } from './ui/chrome.js';
import { effectiveTheme } from './ui/components.js';
import { toast } from './ui/feedback.js';
import { stepBy, syncStepper } from './ui/forms.js';

const outlet = document.getElementById('app');
const store = createStore({ locale: detectLocale(storage.read(STORAGE_KEYS.locale)) });
let teardown = null;
let firstRender = true;

function navigate(path, { replace = false } = {}) {
  const target = `#${path}`;
  if (replace) {
    history.replaceState(null, '', target);
    renderRoute();
  } else if (location.hash === target) {
    renderRoute();
  } else {
    location.hash = path;
  }
}

const app = {
  navigate,
  signedIn(session) {
    toast({ title: t('auth.welcome', { name: session.name }) });
    navigate(HOME[session.role], { replace: true });
  },
  signOut() {
    auth.signOut();
    toast({ tone: 'info', title: t('auth.signedOut') });
    navigate('/');
  },
};

function guard(route, session) {
  if (route.access === 'anonymous' && session) return HOME[session.role];
  if (route.access === 'guest' || route.access === 'host') {
    if (!session) return `/login?role=${route.access}`;
    if (session.role !== route.access) return HOME[session.role];
  }
  return null;
}

function renderRoute() {
  const { path, query } = parseHash();
  const session = auth.getSession();
  const route = routes.find((item) => item.path === path) ?? notFoundRoute;
  const redirect = guard(route, session);
  if (redirect) {
    navigate(redirect, { replace: true });
    return;
  }

  const ctx = { path, query, session, locale: getLocale(), app };
  const content = route.view.render(ctx);
  const page = route.layout === 'app' ? appShell(ctx, content) : content;
  const moveFocus = !firstRender;
  firstRender = false;

  const swap = () => {
    teardown?.();
    // A fresh root per screen: listeners a view attaches to its root are
    // discarded with it, so nothing leaks into the next screen.
    const viewRoot = document.createElement('div');
    viewRoot.className = 'view';
    render(viewRoot, page);
    outlet.replaceChildren(viewRoot);
    document.title = route.view.title(ctx);
    teardown = route.view.mount?.(viewRoot, ctx) ?? null;
    viewRoot.querySelectorAll('[data-stepper]').forEach(syncStepper);
    observeReveals(viewRoot);
    if (moveFocus) {
      window.scrollTo({ top: 0 });
      // Announce the new screen to assistive tech by focusing its heading.
      const heading = outlet.querySelector('h1');
      if (heading) {
        heading.setAttribute('tabindex', '-1');
        heading.focus({ preventScroll: true });
      }
    }
  };
  if (moveFocus) withViewTransition(swap);
  else swap();
}

function applyLocale(code) {
  setLocale(code);
  document.documentElement.lang = code;
  document.querySelector('.skip-link').textContent = t('common.skip');
}

function setTheme(value) {
  if (value !== 'light' && value !== 'dark') return;
  document.documentElement.dataset.theme = value;
  storage.write(STORAGE_KEYS.theme, value);
  document.querySelectorAll('[data-theme-value]').forEach((button) => {
    button.setAttribute('aria-pressed', String(button.dataset.themeValue === value));
  });
}

function toggleTheme() {
  setTheme(effectiveTheme() === 'dark' ? 'light' : 'dark');
}

/** Profile menus: one open at a time; outside click or Escape closes, focus returns to the button. */
function closeProfileMenus(except = null, { restoreFocus = false } = {}) {
  document.querySelectorAll('[data-profile-toggle][aria-expanded="true"]').forEach((button) => {
    if (button === except) return;
    button.setAttribute('aria-expanded', 'false');
    button.parentElement.querySelector('[data-profile-menu]').hidden = true;
    if (restoreFocus) button.focus();
  });
}

function toggleProfileMenu(button) {
  const open = button.getAttribute('aria-expanded') !== 'true';
  closeProfileMenus(button);
  button.setAttribute('aria-expanded', String(open));
  const menu = button.parentElement.querySelector('[data-profile-menu]');
  menu.hidden = !open;
  if (open) menu.querySelector('button')?.focus();
}

function scrollToSection(id) {
  const target = document.getElementById(id);
  if (!target) return;
  target.scrollIntoView({ behavior: prefersReducedMotion() ? 'auto' : 'smooth', block: 'start' });
  const heading = target.querySelector('h2');
  if (heading) {
    heading.setAttribute('tabindex', '-1');
    heading.focus({ preventScroll: true });
  }
}

document.addEventListener('click', (event) => {
  if (!(event.target instanceof Element)) return;
  const action = event.target.closest('[data-action]');
  if (action) {
    switch (action.dataset.action) {
      case 'locale':
        store.set({ locale: action.dataset.locale });
        break;
      case 'theme':
        toggleTheme();
        break;
      case 'theme-set':
        setTheme(action.dataset.themeValue);
        break;
      case 'logout':
        app.signOut();
        break;
      case 'scroll':
        scrollToSection(action.dataset.target);
        break;
      case 'top':
        if (parseHash().path === '/') {
          event.preventDefault();
          window.scrollTo({ top: 0, behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
        }
        break;
      case 'skip':
        event.preventDefault();
        document.getElementById('main')?.focus();
        break;
      default:
        break;
    }
  }
  const step = event.target.closest('[data-step]');
  if (step) stepBy(step);
  const profileButton = event.target.closest('[data-profile-toggle]');
  if (profileButton) toggleProfileMenu(profileButton);
  else if (!event.target.closest('[data-profile-menu]')) closeProfileMenus();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeProfileMenus(null, { restoreFocus: true });
});

document.addEventListener('input', (event) => {
  const stepper = event.target instanceof Element ? event.target.closest('[data-stepper]') : null;
  if (stepper) syncStepper(stepper);
});

store.subscribe((state, previous) => {
  if (state.locale !== previous.locale) {
    storage.write(STORAGE_KEYS.locale, state.locale);
    applyLocale(state.locale);
    renderRoute();
  }
});

// Sign-in or sign-out in another tab: re-evaluate guards here too.
window.addEventListener('storage', (event) => {
  if (event.key === STORAGE_KEYS.session) renderRoute();
});
window.addEventListener('hashchange', renderRoute);

if (!prefersReducedMotion()) document.documentElement.classList.add('motion');
applyLocale(store.get().locale);
initPointerEffects();
renderRoute();
