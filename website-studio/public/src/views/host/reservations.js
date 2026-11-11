/** Host: every reservation across the portfolio (booking view) with filters. */
import { html, render } from '../../core/html.js';
import { t } from '../../core/i18n.js';
import { formatMoney, formatRange, roundMoney, stayStatus } from '../../core/format.js';
import { observeReveals } from '../../core/motion.js';
import { replaceQuery } from '../../core/router.js';
import { bookingService } from '../../services/booking-service.js';
import { pageHead } from '../../ui/chrome.js';
import { avatar, emptyState, errorState, skeletonRows, statusBadge } from '../../ui/components.js';
import { errorCopy } from '../../ui/feedback.js';
import { icon } from '../../ui/icons.js';

const PATH = '/host/reservations';
const STATUSES = ['all', 'upcoming', 'ongoing', 'past'];

function table(rows) {
  return html`<div class="table-wrap reveal"><table class="table">
    <caption class="visually-hidden">${t('host.reservations.title')}</caption>
    <thead><tr>
      <th scope="col">${t('host.reservations.cols.guest')}</th>
      <th scope="col">${t('host.reservations.cols.listing')}</th>
      <th scope="col">${t('host.reservations.cols.dates')}</th>
      <th scope="col" class="num">${t('host.reservations.cols.party')}</th>
      <th scope="col" class="num">${t('common.total')}</th>
      <th scope="col">${t('host.reservations.cols.status')}</th>
    </tr></thead>
    <tbody>${rows.map((booking) => html`<tr>
      <td data-label="${t('host.reservations.cols.guest')}"><span class="guest-cell">${avatar(booking.guestName, 'sm')}<strong>${booking.guestName}</strong></span></td>
      <td data-label="${t('host.reservations.cols.listing')}">${booking.apartmentName}<span class="cell-sub">${booking.city}</span></td>
      <td data-label="${t('host.reservations.cols.dates')}">${formatRange(booking.start, booking.end)}<span class="cell-sub">${t('common.nights', { count: booking.nights })}</span></td>
      <td data-label="${t('host.reservations.cols.party')}" class="num">${booking.people}</td>
      <td data-label="${t('common.total')}" class="num"><strong>${formatMoney(booking.total)}</strong></td>
      <td data-label="${t('host.reservations.cols.status')}">${statusBadge(booking.status)}</td>
    </tr>`)}</tbody>
  </table></div>`;
}

export const reservationsView = {
  title: () => t('host.reservations.metaTitle'),

  render: (ctx) => html`
    ${pageHead({ title: t('host.reservations.title') })}
    <div class="filters">
      <div class="segmented" role="group" aria-label="${t('host.reservations.cols.status')}" data-status>
        ${STATUSES.map((status) => html`<button type="button" class="segmented__btn" data-value="${status}" aria-pressed="${(ctx.query.status ?? 'all') === status}">${status === 'all' ? t('host.reservations.all') : t(`status.${status}`)}</button>`)}
      </div>
      <label><span class="visually-hidden">${t('host.reservations.cols.listing')}</span>
        <select class="select input--pill" data-listing><option value="">${t('host.reservations.allListings')}</option></select>
      </label>
      <label class="input-icon">${icon('search', 16)}<span class="visually-hidden">${t('host.reservations.searchGuest')}</span>
        <input class="input input--pill" type="search" data-guest placeholder="${t('host.reservations.searchGuest')}" value="${ctx.query.guest ?? ''}">
      </label>
    </div>
    <div class="toolbar__summary toolbar__summary--spaced" data-summary aria-live="polite"></div>
    <div data-table aria-busy="true">${skeletonRows(5)}</div>`,

  mount(root, ctx) {
    const state = {
      status: STATUSES.includes(ctx.query.status) ? ctx.query.status : 'all',
      listing: ctx.query.listing ?? '',
      bookings: [], error: null,
    };
    const container = root.querySelector('[data-table]');
    const listingSelect = root.querySelector('[data-listing]');
    const guestInput = root.querySelector('[data-guest]');
    const summaryEl = root.querySelector('[data-summary]');
    const controller = new AbortController();

    const syncUrl = () => replaceQuery(PATH, {
      status: state.status === 'all' ? '' : state.status, listing: state.listing, guest: guestInput.value.trim(),
    });

    const paint = () => {
      container.setAttribute('aria-busy', 'false');
      root.querySelectorAll('[data-status] [data-value]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.value === state.status)));
      if (state.error) {
        summaryEl.textContent = '';
        render(container, errorState(errorCopy(state.error).message));
        return;
      }
      const needle = guestInput.value.trim().toLocaleLowerCase();
      const rows = state.bookings
        .filter((booking) => state.status === 'all' || booking.status === state.status)
        .filter((booking) => !state.listing || booking.apartmentName === state.listing)
        .filter((booking) => !needle || booking.guestName.toLocaleLowerCase().includes(needle));
      const revenue = roundMoney(rows.reduce((sum, booking) => sum + booking.total, 0));
      render(summaryEl, html`<strong>${t('host.reservations.count', { count: rows.length })}</strong><span>${formatMoney(revenue)}</span>`);
      if (!state.bookings.length) {
        render(container, emptyState({ iconName: 'calendar', title: t('host.reservations.empty.title'), body: t('host.reservations.empty.body') }));
      } else if (!rows.length) {
        render(container, emptyState({ iconName: 'search', title: t('explore.noMatch.title'), body: t('host.reservations.noMatch') }));
      } else {
        render(container, table(rows));
      }
      observeReveals(container);
    };

    const load = async () => {
      try {
        const bookings = await bookingService.listBookings({ signal: controller.signal });
        state.bookings = bookings.map((booking) => ({ ...booking, status: stayStatus(booking) }));
        const names = [...new Set(bookings.map((booking) => booking.apartmentName))].sort((a, b) => a.localeCompare(b));
        if (state.listing && !names.includes(state.listing)) state.listing = '';
        render(listingSelect, html`<option value="">${t('host.reservations.allListings')}</option>${names.map((name) => html`<option value="${name}" ${name === state.listing ? 'selected' : ''}>${name}</option>`)}`);
        state.error = null;
      } catch (error) {
        if (error?.name === 'AbortError') return;
        state.error = error;
      }
      paint();
    };

    root.querySelector('[data-status]').addEventListener('click', (event) => {
      const button = event.target.closest('[data-value]');
      if (!button) return;
      state.status = button.dataset.value;
      syncUrl();
      paint();
    });
    listingSelect.addEventListener('change', () => { state.listing = listingSelect.value; syncUrl(); paint(); });
    guestInput.addEventListener('input', () => { syncUrl(); paint(); });
    container.addEventListener('click', (event) => { if (event.target.closest('[data-retry]')) load(); });

    load();
    return () => controller.abort();
  },
};
