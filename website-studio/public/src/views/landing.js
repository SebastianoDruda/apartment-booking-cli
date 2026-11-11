/** Public landing page: one promise, two roles, four guarantees, the live catalogue. */
import { html, render } from '../core/html.js';
import { t, tRich } from '../core/i18n.js';
import { observeReveals } from '../core/motion.js';
import { HOME } from '../config.js';
import { bookingService } from '../services/booking-service.js';
import { publicHeader, siteFooter } from '../ui/chrome.js';
import { stayCard } from '../ui/components.js';
import { icon } from '../ui/icons.js';

const entry = (ctx, role) => (ctx.session?.role === role ? `#${HOME[role]}` : `#/login?role=${role}`);

function hero(ctx) {
  return html`<section class="hero" aria-labelledby="hero-title">
    <div class="aurora" aria-hidden="true"><span></span><span></span><span></span></div>
    <div class="grain" aria-hidden="true"></div>
    <div class="container hero__inner">
      <p class="hero__live" data-live-count><span class="pulse" aria-hidden="true"></span><span data-live-text>&nbsp;</span></p>
      <h1 class="display hero__title" id="hero-title">${tRich('landing.title')}</h1>
      <p class="hero__lead">${t('landing.lead')}</p>
      <div class="hero__ctas">
        <a class="btn btn--primary btn--lg" href="${entry(ctx, 'guest')}">${t('landing.ctaGuest')} ${icon('arrowRight', 18)}</a>
        <a class="btn btn--ghost btn--lg" href="${entry(ctx, 'host')}">${icon('key', 18)} ${t('landing.ctaHost')}</a>
      </div>
    </div>
  </section>`;
}

function sides(ctx) {
  const column = (role, iconName) => html`<article class="side side--${role} reveal">
    <header class="side__head">
      <span class="side__icon">${icon(iconName, 20)}</span>
      <h3 class="display side__title">${t(`landing.sides.${role}.title`)}</h3>
    </header>
    <ol class="steps">
      <li>${t(`landing.sides.${role}.step1`)}</li>
      <li>${t(`landing.sides.${role}.step2`)}</li>
      <li>${t(`landing.sides.${role}.step3`)}</li>
    </ol>
    <a class="btn btn--sm ${role === 'guest' ? 'btn--primary' : 'btn--dark'}" href="${entry(ctx, role)}">
      ${t(`landing.sides.${role}.cta`)} ${icon('arrowRight', 16)}</a>
  </article>`;

  return html`<section class="section" id="how" aria-labelledby="how-title">
    <div class="container">
      <header class="section-head reveal">
        <p class="eyebrow">${t('nav.how')}</p>
        <h2 class="display section-title" id="how-title">${tRich('landing.sides.title')}</h2>
      </header>
      <div class="sides">${column('guest', 'suitcase')}${column('host', 'key')}</div>
    </div>
  </section>`;
}

function features() {
  const item = (key, iconName, wide = false, visual = '') => html`<article class="bento__item spotlight reveal ${wide ? 'bento__item--wide' : ''}">
    <span class="bento__icon">${icon(iconName, 20)}</span>
    ${visual}
    <h3>${t(`landing.features.${key}.title`)}</h3>
    <p>${t(`landing.features.${key}.body`)}</p>
  </article>`;
  const calendar = html`<div class="cal-strip" aria-hidden="true">${'bbffppppffbbbf'.split('').map((kind) => html`<span class="cal-strip__day cal-strip__day--${kind}"></span>`)}</div>`;
  const swap = html`<div class="swap" aria-hidden="true"><span>12–16</span>${icon('arrowRight', 16)}<span class="swap__new">14–19</span></div>`;

  return html`<section class="section section--tint" id="features" aria-labelledby="features-title">
    <div class="container">
      <header class="section-head reveal">
        <p class="eyebrow">${t('nav.features')}</p>
        <h2 class="display section-title" id="features-title">${tRich('landing.features.title')}</h2>
      </header>
      <div class="bento">
        ${item('live', 'calendar', true, calendar)}
        ${item('overlap', 'shield')}
        ${item('price', 'euro')}
        ${item('flex', 'refresh', true, swap)}
      </div>
    </div>
  </section>`;
}

export const landingView = {
  title: () => t('landing.metaTitle'),

  render: (ctx) => html`
    <div class="sheet" id="top">
      ${publicHeader(ctx, { sections: true })}
      <main id="main" tabindex="-1">
        ${hero(ctx)}
        ${sides(ctx)}
        ${features()}
        <section class="section" id="stays" aria-labelledby="stays-title" data-stays hidden>
          <div class="container">
            <header class="section-head section-head--split reveal">
              <div>
                <p class="eyebrow">${t('nav.stays')}</p>
                <h2 class="display section-title" id="stays-title">${tRich('landing.stays.title')}</h2>
              </div>
              <a class="btn btn--ghost btn--sm" href="${entry(ctx, 'guest')}">${t('landing.stays.cta')} ${icon('arrowRight', 16)}</a>
            </header>
            <div class="grid grid--stays grid--three" data-stays-grid></div>
          </div>
        </section>
      </main>
    </div>
    ${siteFooter(ctx)}`,

  mount(root, ctx) {
    const controller = new AbortController();
    const header = root.querySelector('[data-site-header]');
    const onScroll = () => header?.classList.toggle('is-scrolled', window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });

    bookingService.listApartments({ signal: controller.signal }).then((apartments) => {
      if (!apartments.length) return;
      const live = root.querySelector('[data-live-count]');
      live.querySelector('[data-live-text]').textContent = t('landing.live', { count: apartments.length });
      live.classList.add('is-ready');

      const section = root.querySelector('[data-stays]');
      const featured = [...apartments].sort((a, b) => b.pricePerNight - a.pricePerNight).slice(0, 3);
      render(root.querySelector('[data-stays-grid]'), featured.map((apartment) => stayCard(apartment, {
        action: html`<a class="btn btn--soft btn--sm" href="${entry(ctx, 'guest')}">${t('explore.book')}</a>`,
      })));
      section.hidden = false;
      observeReveals(section);
    }).catch(() => { /* The live preview is optional; the page works without the API. */ });

    return () => {
      controller.abort();
      window.removeEventListener('scroll', onScroll);
    };
  },
};
