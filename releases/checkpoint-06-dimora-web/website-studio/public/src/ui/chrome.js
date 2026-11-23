/** Page chrome: public header and footer, the signed-in shell, and page headings. */
import { html } from '../core/html.js';
import { t, tRich } from '../core/i18n.js';
import { HOME, NAV } from '../config.js';
import { brand, langLinks, profileMenu, themeSwitch, themeToggle } from './components.js';
import { icon, logoMark, roleMark } from './icons.js';

const SECTIONS = ['how', 'features', 'stays'];

/** Open over the page at the top; once the page scrolls it draws in to a glass pill (see layout.css). */
export function publicHeader(ctx, { sections = false } = {}) {
  const account = ctx.session
    ? html`<a class="btn btn--primary btn--sm" href="#${HOME[ctx.session.role]}">${t('nav.openSpace')} ${icon('arrowRight', 16)}</a>`
    : html`<a class="btn btn--primary btn--sm" href="#/login">${t('common.signIn')}</a>`;

  return html`<header class="site-header" data-site-header>
    <div class="site-bar">
      ${sections
        ? html`<a class="brand" href="#/" data-action="top" aria-label="Dimora">${logoMark()}<span class="brand__word">Dimora</span></a>`
        : brand()}
      ${sections ? html`<nav class="site-nav" aria-label="${t('nav.sections')}">${SECTIONS.map((id) => html`
        <button type="button" class="site-nav__link" data-action="scroll" data-target="${id}">${t(`nav.${id}`)}</button>`)}
      </nav>` : ''}
      <div class="site-bar__tools">${themeToggle()}${account}</div>
    </div>
  </header>`;
}

/**
 * The landing page is a sheet over this footer: at the end of the page the sheet
 * lifts like a curtain and uncovers it, pinned below (see layout.css).
 */
export function siteFooter(ctx) {
  return html`<footer class="curtain">
    <div class="curtain__band">
      <div class="container curtain__inner">
        <a class="brand brand--light" href="#/" data-action="top" aria-label="${t('footer.top')}">${logoMark()}<span class="brand__word">Dimora</span></a>
        <p class="display curtain__line">${tRich('footer.line')}</p>
        <a class="btn btn--primary btn--lg curtain__cta" href="#/login">${t('landing.cta')} ${icon('arrowRight', 18)}</a>
        <div class="curtain__wordmark" aria-hidden="true"><p>dimora</p></div>
        <div class="curtain__bottom">
          <span>© ${new Date().getFullYear()} Dimora</span>
          <span class="curtain__engine">${t('footer.engine')}</span>
          ${langLinks(ctx.locale, 'on-dark')}
        </div>
      </div>
    </div>
  </footer>`;
}

/** One quiet line at the end of every other screen: copyright and language. */
export function miniFooter(ctx) {
  return html`<footer class="mini-footer">
    <span>© ${new Date().getFullYear()} Dimora</span>
    ${langLinks(ctx.locale)}
  </footer>`;
}

function navLinks(ctx, className) {
  return NAV[ctx.session.role].map((item) => html`<a class="${className}" href="#${item.path}"
    ${ctx.path === item.path ? html`aria-current="page"` : ''}>${icon(item.icon, 18)}<span>${t(item.label)}</span></a>`);
}

/** Signed-in workspace: a side panel (role mark, sections, profile) beside the content. */
export function appShell(ctx, content) {
  const { role } = ctx.session;
  const mark = (size) => html`<a class="sidebar__brand" href="#${HOME[role]}" aria-label="Dimora · ${t(`roles.${role}`)}">
    ${roleMark(role, size)}<span>Dimora<small>${t(`roles.${role}`)}</small></span></a>`;
  return html`<div class="app app--${role}">
    <aside class="sidebar">
      ${mark(36)}
      <nav class="sidebar__nav" aria-label="${t('shell.mainNav')}">${navLinks(ctx, 'sidebar__link')}</nav>
      <div class="dock">${themeSwitch()}${profileMenu(ctx.session)}</div>
    </aside>
    <div class="mobilebar">
      ${mark(32)}
      <div class="dock dock--bar">${themeSwitch()}${profileMenu(ctx.session, { placement: 'down' })}</div>
    </div>
    <main id="main" class="app__main" tabindex="-1">
      <div class="app__content">${content}</div>
      ${miniFooter(ctx)}
    </main>
    <nav class="tabbar" aria-label="${t('shell.mainNav')}">${navLinks(ctx, 'tabbar__link')}</nav>
  </div>`;
}

/** Compact screen heading: the title and, optionally, the screen's main action. */
export function pageHead({ title, actions = '' }) {
  return html`<header class="page-head">
    <h1 class="display page-title">${title}</h1>
    ${actions ? html`<div class="page-head__actions">${actions}</div>` : ''}
  </header>`;
}
