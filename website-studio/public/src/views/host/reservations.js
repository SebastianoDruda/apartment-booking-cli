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
const statusLabel = (status) => (status === 'all' ? t('host.reservations.all') : t(`status.${status}`));

function table(rows) {
  return html`<div class="table-wrap reveal"><table class="table table--reservations">
    <caption class="visually-hidden">${t('host.reservations.title')}</caption>
    <thead><tr>
      <th scope="col">${t('host.reservations.cols.guest')}</th>
      <th scope="col">${t('host.reservations.cols.listing')}</th>
      <th scope="col">${t('host.reservations.cols.dates')}</th>
      <th scope="col" class="num">${t('host.reservations.cols.party')}</th>
      <th scope="col">${t('host.reservations.cols.status')}</th>
      <th scope="col" class="num">${t('common.total')}</th>
    </tr></thead>
    <tbody>${rows.map((booking) => html`<tr>
      <td data-label="${t('host.reservations.cols.guest')}"><span class="guest-cell">${avatar(booking.guestName, 'sm')}<strong>${booking.guestName}</strong></span></td>
      <td data-label="${t('host.reservations.cols.listing')}"><span class="cell-main">${booking.apartmentName}<span class="cell-sub">${booking.city}</span></span></td>
      <td data-label="${t('host.reservations.cols.dates')}"><span class="cell-main">${formatRange(booking.start, booking.end)}<span class="cell-sub">${t('common.nights', { count: booking.nights })}</span></span></td>
      <td data-label="${t('host.reservations.cols.party')}" class="num">${booking.people}</td>
      <td data-label="${t('host.reservations.cols.status')}">${statusBadge(booking.status)}</td>
      <td data-label="${t('common.total')}" class="num"><strong>${formatMoney(booking.total)}</strong></td>
    </tr>`)}</tbody>
  </table></div>`;
}

export const reservationsView = {
  title: () => t('host.reservations.metaTitle'),

  render: (ctx) => html`
    ${pageHead({ title: t('host.reservations.title') })}
    <div class="toolbar">
      <div class="toolbar__summary" data-summary aria-live="polite"></div>
      <div class="filter-menu" data-filter-menu>
        <button type="button" class="btn btn--ghost btn--sm filter-menu__toggle" data-filter-toggle aria-expanded="false" aria-controls="res-filters">
          ${icon('filter', 16)} ${t('host.reservations.filters')}<span class="filter-menu__count" data-filter-count hidden></span>
        </button>
        <div class="filter-menu__panel" id="res-filters" role="group" aria-label="${t('host.reservations.filters')}" hidden>
          <label class="field">
            <span class="label">${t('host.reservations.cols.guest')}</span>
            <span class="input-icon">${icon('search', 16)}
              <input class="input" type="search" data-guest placeholder="${t('host.reservations.searchGuest')}" aria-label="${t('host.reservations.searchGuest')}" value="${ctx.query.guest ?? ''}">
            </span>
          </label>
          <div class="field">
            <span class="label" id="res-status">${t('host.reservations.cols.status')}</span>
            <div class="choice-list" role="group" aria-labelledby="res-status" data-status>
              ${STATUSES.map((status) => html`<button type="button" class="choice" data-value="${status}" aria-pressed="${(ctx.query.status ?? 'all') === status}">${statusLabel(status)}</button>`)}
            </div>
          </div>
          <label class="field">
            <span class="label">${t('host.reservations.cols.listing')}</span>
            <select class="select input" data-listing><option value="">${t('host.reservations.allListings')}</option></select>
          </label>
          <div class="filter-menu__foot">
            <button type="button" class="btn btn--quiet btn--sm" data-clear>${t('host.reservations.clear')}</button>
            <button type="button" class="btn btn--primary btn--sm" data-filter-done>${t('host.reservations.done')}</button>
          </div>
        </div>
      </div>
    </div>
    <div class="chips" data-chips hidden></div>
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
    const chipsEl = root.querySelector('[data-chips]');
    const countEl = root.querySelector('[data-filter-count]');
    const menu = root.querySelector('[data-filter-menu]');
    const toggle = root.querySelector('[data-filter-toggle]');
    const panel = root.querySelector('#res-filters');
    const controller = new AbortController();

    const setOpen = (open, { restoreFocus = false } = {}) => {
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      if (open) panel.querySelector('input, button, select')?.focus();
      else if (restoreFocus) toggle.focus();
    };
    const active = () => [
      guestInput.value.trim() && { key: 'guest', label: `${t('host.reservations.cols.guest')}: ${guestInput.value.trim()}` },
      state.status !== 'all' && { key: 'status', label: statusLabel(state.status) },
      state.listing && { key: 'listing', label: state.listing },
    ].filter(Boolean);

    const syncUrl = () => replaceQuery(PATH, {
      status: state.status === 'all' ? '' : state.status, listing: state.listing, guest: guestInput.value.trim(),
    });

    const paint = () => {
      container.setAttribute('aria-busy', 'false');
      root.querySelectorAll('[data-status] [data-value]').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.value === state.status)));
      const filters = active();
      countEl.hidden = !filters.length;
      countEl.textContent = String(filters.length);
      chipsEl.hidden = !filters.length;
      render(chipsEl, filters.map((filter) => html`<button type="button" class="chip" data-remove="${filter.key}" aria-label="${t('host.reservations.removeFilter', { name: filter.label })}">${filter.label}${icon('x', 14)}</button>`));
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

    const clear = (key) => {
      if (!key || key === 'guest') guestInput.value = '';
      if (!key || key === 'status') state.status = 'all';
      if (!key || key === 'listing') { state.listing = ''; listingSelect.value = ''; }
      syncUrl();
      paint();
    };
    toggle.addEventListener('click', () => setOpen(panel.hidden));
    root.querySelector('[data-filter-done]').addEventListener('click', () => setOpen(false, { restoreFocus: true }));
    root.querySelector('[data-clear]').addEventListener('click', () => clear());
    chipsEl.addEventListener('click', (event) => {
      const chip = event.target.closest('[data-remove]');
      if (chip) clear(chip.dataset.remove);
    });
    const onOutside = (event) => { if (!panel.hidden && !menu.contains(event.target)) setOpen(false); };
    const onKey = (event) => { if (event.key === 'Escape' && !panel.hidden) setOpen(false, { restoreFocus: true }); };
    document.addEventListener('click', onOutside);
    document.addEventListener('keydown', onKey);

    load();
    return () => {
      controller.abort();
      document.removeEventListener('click', onOutside);
      document.removeEventListener('keydown', onKey);
    };
  },
};
