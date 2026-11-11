/** Host: portfolio dashboard — key figures, a 30-day stay timeline, next arrivals and revenue by month. */
import { html, render } from '../../core/html.js';
import { t, tRich } from '../../core/i18n.js';
import {
  addDays, firstName, formatDate, formatMoney, formatNumber, formatRange, nightsBetween, overlapNights, roundMoney, stayStatus, todayIso,
} from '../../core/format.js';
import { countUp, observeReveals } from '../../core/motion.js';
import { bookingService } from '../../services/booking-service.js';
import { pageHead } from '../../ui/chrome.js';
import { avatar, emptyState, errorState, skeletonRows } from '../../ui/components.js';
import { errorCopy } from '../../ui/feedback.js';
import { icon } from '../../ui/icons.js';
import { openListingDialog } from './listing-dialogs.js';

const WINDOW_DAYS = 30;
const MONTHS = 6;

const monthKey = (iso) => iso.slice(0, 7);
function nextMonths(today, count) {
  const [year, month] = today.split('-').map(Number);
  return Array.from({ length: count }, (_, index) => {
    const date = new Date(Date.UTC(year, month - 1 + index, 1));
    return date.toISOString().slice(0, 7);
  });
}

/** Everything the dashboard shows, derived from the two API lists (pure, unit-tested). */
export function portfolioStats(apartments, bookings, today = todayIso()) {
  const active = bookings.filter((booking) => stayStatus(booking, today) !== 'past');
  const horizon = addDays(today, WINDOW_DAYS);
  const rows = apartments.map((apartment) => {
    const stays = bookings
      .filter((booking) => booking.apartmentId === apartment.id && overlapNights(booking.start, booking.end, today, horizon) > 0)
      .sort((a, b) => a.start.localeCompare(b.start))
      .map((booking) => ({
        ...booking,
        offset: booking.start > today ? nightsBetween(today, booking.start) : 0,
        length: overlapNights(booking.start, booking.end, today, horizon),
        cutStart: booking.start < today,
        cutEnd: booking.end > horizon,
      }));
    const nights = stays.reduce((sum, stay) => sum + stay.length, 0);
    return { name: apartment.name, city: apartment.city ?? '', percent: Math.round((nights / WINDOW_DAYS) * 100), nights, stays };
  }).sort((a, b) => b.percent - a.percent || a.name.localeCompare(b.name));
  const bookedNights = rows.reduce((sum, row) => sum + row.nights, 0);
  const months = nextMonths(today, MONTHS).map((key) => ({
    key,
    revenue: roundMoney(bookings.filter((booking) => monthKey(booking.start) === key).reduce((sum, booking) => sum + booking.total, 0)),
  }));
  return {
    listings: apartments.length,
    upcoming: active.length,
    guests: active.reduce((sum, booking) => sum + booking.people, 0),
    revenue: roundMoney(bookings.reduce((sum, booking) => sum + booking.total, 0)),
    occupancy: apartments.length ? Math.round((bookedNights / (apartments.length * WINDOW_DAYS)) * 100) : 0,
    arrivals: bookings.filter((booking) => booking.start >= today).sort((a, b) => a.start.localeCompare(b.start)).slice(0, 5),
    timeline: { rows, ticks: [0, 7, 14, 21, 28].map((day) => ({ day, iso: addDays(today, day) })) },
    months,
  };
}

const pct = (part, whole) => ((part / whole) * 100).toFixed(3);

/** One strip of figures instead of a row of half-empty cards. */
function figures(stats) {
  const figure = (key, value, format, extra = '') => html`<div class="figure">
    <dt>${t(`host.overview.kpi.${key}`)}</dt>
    <dd><span data-count="${value}" data-format="${format}">0</span>${extra}</dd>
  </div>`;
  return html`<dl class="figures reveal" aria-label="${t('host.overview.kpiLabel')}">
    ${figure('revenue', stats.revenue, 'money')}
    ${figure('upcoming', stats.upcoming, 'number')}
    ${figure('guests', stats.guests, 'number')}
    ${figure('occupancy', stats.occupancy, 'number', html`<small>%</small>`)}
  </dl>`;
}

/** Gantt-style view: each listing is a row, each stay a bar across the next 30 days. */
function timeline({ rows, ticks }) {
  return html`<section class="panel timeline reveal" aria-labelledby="timeline-title">
    <header class="panel__head">
      <h2 id="timeline-title">${t('host.overview.timeline')}</h2>
      <a class="btn btn--quiet btn--sm" href="#/host/reservations">${t('host.overview.viewAll')} ${icon('arrowRight', 16)}</a>
    </header>
    ${rows.length ? html`<div class="timeline__scroll"><div class="timeline__grid">
      <div class="timeline__axis" aria-hidden="true">
        <span></span>
        <div class="timeline__ticks">${ticks.map((tick) => html`<span class="timeline__tick" data-x="${pct(tick.day, WINDOW_DAYS)}">${tick.day === 0 ? t('host.overview.today') : formatDate(tick.iso, { day: 'numeric', month: 'short' })}</span>`)}</div>
        <span class="timeline__occ">${t('host.overview.occupied')}</span>
      </div>
      ${rows.map((row) => html`<div class="timeline__row">
        <div class="timeline__label"><strong>${row.name}</strong><span>${row.city}</span></div>
        <ul class="timeline__track" aria-label="${row.name}">
          ${ticks.map((tick) => html`<li class="timeline__rule" data-x="${pct(tick.day, WINDOW_DAYS)}" aria-hidden="true"></li>`)}
          ${row.stays.map((stay) => html`<li class="stay-bar ${stay.cutStart ? 'is-cut-start' : ''} ${stay.cutEnd ? 'is-cut-end' : ''}"
            data-x="${pct(stay.offset, WINDOW_DAYS)}" data-w="${pct(stay.length, WINDOW_DAYS)}" tabindex="0"
            data-tip="${stay.guestName} · ${formatRange(stay.start, stay.end)}"
            aria-label="${stay.guestName}, ${formatRange(stay.start, stay.end)}, ${t('common.guests', { count: stay.people })}"><span>${stay.guestName}</span></li>`)}
        </ul>
        <span class="timeline__pct">${row.percent}%</span>
      </div>`)}
    </div></div>` : html`<p class="panel__empty">${icon('home', 18)} ${t('host.overview.occupancyEmpty')}</p>`}
  </section>`;
}

function arrivals(list) {
  return html`<section class="panel reveal" aria-labelledby="arrivals-title">
    <header class="panel__head"><h2 id="arrivals-title">${t('host.overview.arrivals')}</h2></header>
    ${list.length ? html`<ul class="arrivals">${list.map((booking) => html`<li class="arrival">
      <span class="datebadge"><b>${formatDate(booking.start, { day: 'numeric' })}</b><span>${formatDate(booking.start, { month: 'short' })}</span></span>
      <span class="arrival__who">${avatar(booking.guestName, 'sm')}<span><strong>${booking.guestName}</strong><span class="muted">${booking.apartmentName}</span></span></span>
      <span class="arrival__meta">${t('common.nights', { count: booking.nights })}<span class="muted">${t('common.guests', { count: booking.people })}</span></span>
    </li>`)}</ul>` : html`<p class="panel__empty">${icon('calendar', 18)} ${t('host.overview.arrivalsEmpty')}</p>`}
  </section>`;
}

/** Column chart: booked revenue by check-in month. Only the peak is labelled; every column has a tooltip. */
function revenueChart(months) {
  const max = Math.max(...months.map((month) => month.revenue));
  const peak = max > 0 ? months.findIndex((month) => month.revenue === max) : -1;
  return html`<section class="panel reveal" aria-labelledby="revenue-title">
    <header class="panel__head"><h2 id="revenue-title">${t('host.overview.revenueChart')}</h2></header>
    <ol class="columns" aria-label="${t('host.overview.revenueChart')}">
      ${months.map((month, index) => {
        const label = formatDate(`${month.key}-01`, { month: 'long', year: 'numeric' });
        return html`<li class="column ${index === peak ? 'is-peak' : ''}" tabindex="0" aria-label="${label}: ${formatMoney(month.revenue)}">
          <span class="column__plot"><span class="column__bar" data-tip="${formatMoney(month.revenue)}" data-h="${max ? pct(month.revenue, max) : 0}">${index === peak ? html`<b>${formatMoney(month.revenue)}</b>` : ''}</span></span>
          <span class="column__label" aria-hidden="true">${formatDate(`${month.key}-01`, { month: 'short' })}</span>
        </li>`;
      })}
    </ol>
  </section>`;
}

function dashboard(stats) {
  return html`
    ${figures(stats)}
    ${timeline(stats.timeline)}
    <div class="dash">${arrivals(stats.arrivals)}${revenueChart(stats.months)}</div>`;
}

export const overviewView = {
  title: () => t('host.overview.metaTitle'),

  render: (ctx) => html`
    ${pageHead({ title: tRich('host.overview.title', { name: firstName(ctx.session.name) }) })}
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
          requestAnimationFrame(() => container.querySelectorAll('.column__bar, .stay-bar').forEach((mark) => mark.classList.add('is-drawn')));
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
