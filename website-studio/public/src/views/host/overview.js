/** Host: portfolio dashboard — KPIs, next arrivals and 30-day occupancy. */
import { html, render } from '../../core/html.js';
import { t, tRich } from '../../core/i18n.js';
import {
  addDays, firstName, formatDate, formatMoney, formatNumber, overlapNights, roundMoney, stayStatus, todayIso,
} from '../../core/format.js';
import { countUp, observeReveals } from '../../core/motion.js';
import { bookingService } from '../../services/booking-service.js';
import { pageHead } from '../../ui/chrome.js';
import { avatar, emptyState, errorState, skeletonRows } from '../../ui/components.js';
import { errorCopy } from '../../ui/feedback.js';
import { icon } from '../../ui/icons.js';
import { openListingDialog } from './listing-dialogs.js';

const WINDOW_DAYS = 30;

export function portfolioStats(apartments, bookings, today = todayIso()) {
  const active = bookings.filter((booking) => stayStatus(booking, today) !== 'past');
  const horizon = addDays(today, WINDOW_DAYS);
  return {
    listings: apartments.length,
    upcoming: active.length,
    guests: active.reduce((sum, booking) => sum + booking.people, 0),
    revenue: roundMoney(bookings.reduce((sum, booking) => sum + booking.total, 0)),
    arrivals: bookings.filter((booking) => booking.start >= today).sort((a, b) => a.start.localeCompare(b.start)).slice(0, 5),
    occupancy: apartments.map((apartment) => {
      const nights = bookings
        .filter((booking) => booking.apartmentId === apartment.id)
        .reduce((sum, booking) => sum + overlapNights(booking.start, booking.end, today, horizon), 0);
      return { name: apartment.name, percent: Math.round((nights / WINDOW_DAYS) * 100) };
    }).sort((a, b) => b.percent - a.percent).slice(0, 6),
  };
}

function kpi(key, iconName, value, format) {
  return html`<div class="kpi reveal">
    <div class="kpi__head"><span class="kpi__icon">${icon(iconName, 17)}</span><p class="kpi__label">${t(`host.overview.kpi.${key}`)}</p></div>
    <p class="kpi__value" data-count="${value}" data-format="${format}">0</p>
  </div>`;
}

function dashboard(stats) {
  return html`
    <section class="kpis" aria-label="${t('host.overview.kpiLabel')}">
      ${kpi('listings', 'home', stats.listings, 'number')}
      ${kpi('upcoming', 'calendar', stats.upcoming, 'number')}
      ${kpi('guests', 'users', stats.guests, 'number')}
      ${kpi('revenue', 'euro', stats.revenue, 'money')}
    </section>
    <div class="dash">
      <section class="panel reveal" aria-labelledby="arrivals-title">
        <header class="panel__head">
          <h2 id="arrivals-title">${t('host.overview.arrivals')}</h2>
          <a class="btn btn--quiet btn--sm" href="#/host/reservations">${t('host.overview.viewAll')} ${icon('arrowRight', 16)}</a>
        </header>
        ${stats.arrivals.length ? html`<ul class="arrivals">${stats.arrivals.map((booking) => html`<li class="arrival">
          <span class="datebadge"><b>${formatDate(booking.start, { day: 'numeric' })}</b><span>${formatDate(booking.start, { month: 'short' })}</span></span>
          <span class="arrival__who">${avatar(booking.guestName, 'sm')}<span><strong>${booking.guestName}</strong><span class="muted">${booking.apartmentName}</span></span></span>
          <span class="arrival__meta">${t('common.nights', { count: booking.nights })}<span class="muted">${t('common.guests', { count: booking.people })}</span></span>
        </li>`)}</ul>` : html`<p class="panel__empty">${icon('calendar', 18)} ${t('host.overview.arrivalsEmpty')}</p>`}
      </section>
      <section class="panel reveal" aria-labelledby="occupancy-title">
        <header class="panel__head"><h2 id="occupancy-title">${t('host.overview.occupancy')}</h2></header>
        ${stats.occupancy.length ? html`<ul class="meters">${stats.occupancy.map((row) => html`<li class="meter">
          <div class="meter__head"><span>${row.name}</span><span>${row.percent}%</span></div>
          <div class="meter__track" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${row.percent}" aria-label="${row.name}">
            <span class="meter__fill" data-meter="${row.percent}"></span>
          </div>
        </li>`)}</ul>` : html`<p class="panel__empty">${icon('home', 18)} ${t('host.overview.occupancyEmpty')}</p>`}
      </section>
    </div>`;
}

export const overviewView = {
  title: () => t('host.overview.metaTitle'),

  render: (ctx) => html`
    ${pageHead({
      title: tRich('host.overview.title', { name: firstName(ctx.session.name) }),
      actions: html`<button type="button" class="btn btn--primary" data-add>${icon('plus', 18)} ${t('host.listings.add')}</button>`,
    })}
    <div data-dashboard aria-busy="true">${skeletonRows(4)}</div>`,

  mount(root) {
    const container = root.querySelector('[data-dashboard]');
    const controller = new AbortController();

    const load = async () => {
      try {
        const [apartments, bookings] = await Promise.all([
          bookingService.listApartments({ signal: controller.signal }),
          bookingService.listBookings({ signal: controller.signal }),
        ]);
        container.setAttribute('aria-busy', 'false');
        if (!apartments.length) {
          render(container, emptyState({
            iconName: 'home', title: t('host.listings.empty.title'), body: t('host.listings.empty.body'),
            action: html`<button type="button" class="btn btn--primary" data-add>${icon('plus', 18)} ${t('host.listings.empty.cta')}</button>`,
          }));
        } else {
          render(container, dashboard(portfolioStats(apartments, bookings)));
          container.querySelectorAll('[data-count]').forEach((element) => {
            const format = element.dataset.format === 'money' ? formatMoney : formatNumber;
            countUp(element, Number(element.dataset.count), (value) => format(element.dataset.format === 'money' ? roundMoney(value) : value));
          });
          requestAnimationFrame(() => container.querySelectorAll('.meter__fill').forEach((fill) => fill.classList.add('is-filled')));
        }
      } catch (error) {
        if (error?.name === 'AbortError') return;
        container.setAttribute('aria-busy', 'false');
        render(container, errorState(errorCopy(error).message));
      }
      observeReveals(container);
    };

    root.addEventListener('click', async (event) => {
      if (event.target.closest('[data-retry]')) load();
      if (event.target.closest('[data-add]') && (await openListingDialog())) load();
    });

    load();
    return () => controller.abort();
  },
};
