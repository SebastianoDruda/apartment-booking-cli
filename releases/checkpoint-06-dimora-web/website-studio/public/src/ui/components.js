/** Small presentational building blocks shared by every view. */
import { html } from '../core/html.js';
import { LOCALES, t } from '../core/i18n.js';
import { formatMoney, initials } from '../core/format.js';
import { icon, logoMark } from './icons.js';
import { cover } from './cover.js';

export function brand(href = '#/') {
  return html`<a class="brand" href="${href}" aria-label="Dimora">${logoMark()}<span class="brand__word">Dimora</span></a>`;
}

/** Language choice as plain text links (no pill), shown once per page in the footer. */
export function langLinks(current, tone = '') {
  return html`<div class="lang-links ${tone ? `lang-links--${tone}` : ''}" role="group" aria-label="${t('common.language')}">
    ${icon('globe', 15)}${Object.entries(LOCALES).map(([code, locale]) => html`<button type="button" class="lang-link"
      data-action="locale" data-locale="${code}" lang="${code}" aria-pressed="${code === current}">${locale.label}</button>`)}
  </div>`;
}

export function themeToggle() {
  return html`<button type="button" class="btn btn--icon btn--quiet theme-toggle" data-action="theme"
    aria-label="${t('common.theme')}" title="${t('common.theme')}">${icon('moon', 18)}${icon('sun', 18)}</button>`;
}

export function effectiveTheme() {
  const root = globalThis.document?.documentElement;
  if (root?.dataset.theme) return root.dataset.theme;
  return globalThis.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

/** Light / dark as two explicit choices (sun, moon). */
export function themeSwitch() {
  const current = effectiveTheme();
  return html`<div class="dock__group" role="group" aria-label="${t('common.theme')}">${[['light', 'sun'], ['dark', 'moon']].map(
    ([value, iconName]) => html`<button type="button" class="dock__btn" data-action="theme-set" data-theme-value="${value}"
      aria-pressed="${value === current}" aria-label="${t(`common.themes.${value}`)}" title="${t(`common.themes.${value}`)}">${icon(iconName, 17)}</button>`,
  )}</div>`;
}

/** Profile button with a small menu: who is signed in, and sign out. */
export function profileMenu(session, { placement = 'up' } = {}) {
  return html`<div class="profile profile--${placement}">
    <button type="button" class="dock__btn dock__btn--solo" data-profile-toggle aria-expanded="false" aria-haspopup="true"
      aria-label="${t('common.profile')}" title="${t('common.profile')}">${icon('user', 17)}</button>
    <div class="profile__menu" data-profile-menu hidden>
      <div class="profile__who">${avatar(session.name)}<span><strong>${session.name}</strong><span>${t(`roles.${session.role}`)}</span></span></div>
      <button type="button" class="profile__item" data-action="logout">${icon('logout', 16)} ${t('common.signOut')}</button>
    </div>
  </div>`;
}

export function avatar(name, size = '') {
  return html`<span class="avatar ${size ? `avatar--${size}` : ''}" aria-hidden="true">${initials(name)}</span>`;
}

export function stepper({ name, value = 1, min = 1, max = 30, id = '', labelledby = '' }) {
  return html`<div class="stepper" data-stepper>
    <button type="button" class="stepper__btn" data-step="-1" aria-label="${t('common.decrease')}">${icon('minus', 16)}</button>
    <input class="stepper__input" type="number" inputmode="numeric" name="${name}" ${id ? html`id="${id}"` : ''}
      value="${value}" min="${min}" max="${max}" step="1" ${labelledby ? html`aria-labelledby="${labelledby}"` : ''}>
    <button type="button" class="stepper__btn" data-step="1" aria-label="${t('common.increase')}">${icon('plus', 16)}</button>
  </div>`;
}

export function statusBadge(status) {
  return html`<span class="badge badge--${status}">${t(`status.${status}`)}</span>`;
}

export function emptyState({ iconName = 'sparkles', title, body, action = '' }) {
  return html`<div class="empty reveal">
    <span class="empty__icon">${icon(iconName, 26)}</span>
    <h2 class="empty__title">${title}</h2>
    ${body ? html`<p>${body}</p>` : ''}
    ${action}
  </div>`;
}

export function errorState(message) {
  return emptyState({
    iconName: 'alert',
    title: t('errors.loadFailed'),
    body: message,
    action: html`<button type="button" class="btn btn--primary" data-retry>${icon('refresh', 18)} ${t('common.retry')}</button>`,
  });
}

export function skeletonCards(count = 6) {
  return Array.from({ length: count }, () => html`<div class="stay stay--skeleton" aria-hidden="true">
    <div class="skeleton skeleton--cover"></div>
    <div class="stay__body"><div class="skeleton skeleton--line"></div><div class="skeleton skeleton--line skeleton--short"></div></div>
  </div>`);
}

export function skeletonRows(count = 4) {
  return html`<div class="skeleton-stack" aria-hidden="true">${Array.from({ length: count }, () => html`<div class="skeleton skeleton--row"></div>`)}</div>`;
}

export const place = (apartment) => [apartment.city, apartment.country].filter(Boolean).join(', ') || apartment.address;

/**
 * Apartment card used on the landing page, in search results and in host listings.
 * Head: name and place left, price right. Foot: key facts left, the action right.
 */
export function stayCard(apartment, { action = '', facts = '' } = {}) {
  const withTotal = apartment.total != null;
  return html`<article class="stay reveal">
    <div class="stay__media">${cover(apartment, { monogram: false })}</div>
    <div class="stay__body">
      <div class="stay__head">
        <div class="stay__title">
          <h3 class="stay__name">${apartment.name}</h3>
          <p class="stay__place">${place(apartment)}</p>
        </div>
        <p class="stay__price">${withTotal
          ? html`<strong>${formatMoney(apartment.total)}</strong><span>${t('common.nights', { count: apartment.nights })}</span>`
          : html`<strong>${formatMoney(apartment.pricePerNight)}</strong><span>${t('common.perNight')}</span>`}</p>
      </div>
      <div class="stay__foot">
        <p class="stay__facts">${facts || html`${icon('users', 15)} ${t('common.upTo', { count: apartment.maxPeople })}`}</p>
        ${action}
      </div>
    </div>
  </article>`;
}
