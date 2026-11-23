/** Toasts, dialogs and error copy: the system's voice when something happens. */
import { html, render } from '../core/html.js';
import { has, t } from '../core/i18n.js';
import { ApiError } from '../services/api.js';
import { icon } from './icons.js';

const TOAST_ICONS = { success: 'check', error: 'alert', info: 'sparkles' };

export function toast({ tone = 'success', title, message = '', timeout = 4800 }) {
  const region = document.getElementById('toasts');
  if (!region) return;
  const node = document.createElement('div');
  node.className = `toast toast--${tone}`;
  node.setAttribute('role', tone === 'error' ? 'alert' : 'status');
  render(node, html`
    <span class="toast__icon">${icon(TOAST_ICONS[tone] ?? 'sparkles', 16)}</span>
    <div class="toast__text"><p class="toast__title">${title}</p>${message ? html`<p class="toast__msg">${message}</p>` : ''}</div>
    <button type="button" class="toast__close" aria-label="${t('common.close')}">${icon('x', 16)}</button>`);

  let timer;
  const dismiss = () => {
    clearTimeout(timer);
    node.classList.add('is-leaving');
    node.addEventListener('animationend', () => node.remove(), { once: true });
    setTimeout(() => node.remove(), 400);
  };
  node.querySelector('.toast__close').addEventListener('click', dismiss);
  node.addEventListener('pointerenter', () => clearTimeout(timer));
  node.addEventListener('pointerleave', () => { timer = setTimeout(dismiss, 2000); });
  region.append(node);
  timer = setTimeout(dismiss, timeout);
}

/** Map an error to localised copy. `overrides` supplies context-specific messages per code. */
export function errorCopy(error, overrides = {}) {
  if (!(error instanceof ApiError)) {
    return { title: t('errors.titles.generic'), message: t('errors.generic') };
  }
  const titleKey = `errors.titles.${error.code}`;
  const offline = error.code === 'network' || error.code === 'api_unreachable';
  return {
    title: has(titleKey) ? t(titleKey) : t('errors.titles.generic'),
    message: overrides[error.code] ?? (offline ? t('errors.offline') : error.message),
  };
}

export function toastError(error, overrides) {
  toast({ tone: 'error', ...errorCopy(error, overrides) });
}

let dialogCount = 0;

/**
 * Open a modal built on the native <dialog> element (focus trapping, Escape,
 * top layer). Resolves with the value passed to `close`, or null if dismissed.
 */
export function openDialog({ title, description = '', content, size = 'md', onMount }) {
  const previousFocus = document.activeElement;
  const id = `dialog-${++dialogCount}`;
  const dialog = document.createElement('dialog');
  dialog.className = `dialog dialog--${size}`;
  dialog.setAttribute('aria-labelledby', `${id}-title`);
  if (description) dialog.setAttribute('aria-describedby', `${id}-desc`);

  render(dialog, html`<div class="dialog__panel">
    <header class="dialog__head">
      <div>
        <h2 class="dialog__title" id="${id}-title">${title}</h2>
        ${description ? html`<p class="dialog__desc" id="${id}-desc">${description}</p>` : ''}
      </div>
      <button type="button" class="btn btn--icon btn--quiet" data-close aria-label="${t('common.close')}">${icon('x', 18)}</button>
    </header>
    <div class="dialog__body">${content}</div>
  </div>`);

  document.body.append(dialog);

  return new Promise((resolve) => {
    let closed = false;
    // Navigating away (back button, links) dismisses the modal with the page it belongs to.
    const onNavigate = () => close(null);
    window.addEventListener('hashchange', onNavigate);
    const close = (value = null) => {
      if (closed) return;
      closed = true;
      window.removeEventListener('hashchange', onNavigate);
      dialog.classList.add('is-closing');
      setTimeout(() => {
        dialog.close();
        dialog.remove();
        if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
        resolve(value);
      }, 170);
    };
    dialog.addEventListener('cancel', (event) => { event.preventDefault(); close(null); });
    dialog.addEventListener('click', (event) => {
      if (event.target === dialog || event.target.closest('[data-close]')) close(null);
    });
    dialog.showModal();
    onMount?.(dialog, close);
  });
}

export function confirmDialog({ title, message, confirmLabel, cancelLabel = t('common.cancel'), tone = 'danger', requireText = '' }) {
  return openDialog({
    title,
    size: 'sm',
    content: html`<form class="confirm" novalidate data-confirm>
      <p class="dialog__text">${message}</p>
      ${requireText ? html`<div class="field">
        <label class="label" for="confirm-text">${t('common.typeToConfirm', { text: requireText })}</label>
        <input class="input" id="confirm-text" autocomplete="off" spellcheck="false" autofocus>
      </div>` : ''}
      <div class="dialog__actions">
        <button type="button" class="btn btn--ghost" data-close ${requireText ? '' : 'autofocus'}>${cancelLabel}</button>
        <button type="submit" class="btn ${tone === 'danger' ? 'btn--danger' : 'btn--primary'}" ${requireText ? 'disabled' : ''}>${confirmLabel}</button>
      </div>
    </form>`,
    onMount(dialog, close) {
      const form = dialog.querySelector('[data-confirm]');
      const submit = form.querySelector('[type="submit"]');
      const input = form.querySelector('#confirm-text');
      input?.addEventListener('input', () => {
        submit.disabled = input.value.trim().toLocaleLowerCase() !== requireText.toLocaleLowerCase();
      });
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!submit.disabled) close(true);
      });
    },
  }).then(Boolean);
}
