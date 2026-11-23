/** Guest: browse the catalogue and search live availability (apartment view/search, booking create). */
import { html, render } from '../../core/html.js';
import { t, tRich } from '../../core/i18n.js';
import { addDays, firstName, formatRange, todayIso } from '../../core/format.js';
import { observeReveals } from '../../core/motion.js';
import { replaceQuery } from '../../core/router.js';
import { MAX_GUESTS } from '../../config.js';
import { bookingService } from '../../services/booking-service.js';
import { pageHead } from '../../ui/chrome.js';
import { emptyState, errorState, skeletonCards, stayCard, stepper } from '../../ui/components.js';
import { errorCopy, toast } from '../../ui/feedback.js';
import { showAlert } from '../../ui/forms.js';
import { icon } from '../../ui/icons.js';
import { openBookingDialog } from './stay-dialogs.js';

const PATH = '/guest/explore';
const SORTS = ['priceAsc', 'priceDesc', 'capacity', 'name'];
const ISO = /^\d{4}-\d{2}-\d{2}$/;

function readCriteria(query) {
  const guests = Number.parseInt(query.guests, 10);
  return {
    start: ISO.test(query.start ?? '') ? query.start : '',
    end: ISO.test(query.end ?? '') ? query.end : '',
    guests: Number.isInteger(guests) && guests > 0 ? Math.min(guests, MAX_GUESTS) : 1,
    q: query.q ?? '',
    sort: SORTS.includes(query.sort) ? query.sort : 'priceAsc',
  };
}

const COMPARE = {
  priceAsc: (a, b) => a.pricePerNight - b.pricePerNight,
  priceDesc: (a, b) => b.pricePerNight - a.pricePerNight,
  capacity: (a, b) => b.maxPeople - a.maxPeople || a.pricePerNight - b.pricePerNight,
  name: (a, b) => a.name.localeCompare(b.name),
};

export const exploreView = {
  title: () => t('explore.metaTitle'),

  render(ctx) {
    const criteria = readCriteria(ctx.query);
    const today = todayIso();
    return html`
      ${pageHead({ title: tRich('explore.title', { name: firstName(ctx.session.name) }) })}
      <form class="filterbar reveal" role="search" novalidate data-search aria-label="${t('explore.searchLabel')}">
        <label class="filterbar__field filterbar__field--where">
          <span class="filterbar__label">${t('explore.where')}</span>
          <span class="filterbar__control">${icon('search', 16)}
            <input type="search" name="q" data-filter placeholder="${t('explore.filter')}" value="${criteria.q}" autocomplete="off">
          </span>
        </label>
        <label class="filterbar__field">
          <span class="filterbar__label">${t('explore.checkIn')}</span>
          <input type="date" name="start" min="${today}" value="${criteria.start}">
        </label>
        <label class="filterbar__field">
          <span class="filterbar__label">${t('explore.checkOut')}</span>
          <input type="date" name="end" min="${addDays(criteria.start || today, 1)}" value="${criteria.end}">
        </label>
        <div class="filterbar__field filterbar__field--guests">
          <span class="filterbar__label" id="search-guests">${t('explore.guests')}</span>
          ${stepper({ name: 'guests', value: criteria.guests, min: 1, max: MAX_GUESTS, labelledby: 'search-guests' })}
        </div>
      </form>
      <p class="form-alert" role="alert" data-search-error hidden></p>

      <div class="toolbar">
        <div class="toolbar__summary" data-summary aria-live="polite"></div>
        <div class="toolbar__controls">
          <button type="button" class="btn btn--quiet btn--sm" data-reset hidden>${icon('x', 16)} ${t('explore.reset')}</button>
          <label class="sort">
            <span class="sort__label">${t('explore.sort')}</span>
            <select class="sort__select" data-sort>${SORTS.map((sort) => html`<option value="${sort}" ${sort === criteria.sort ? 'selected' : ''}>${t(`explore.sorts.${sort}`)}</option>`)}</select>
          </label>
        </div>
      </div>
      <div class="grid grid--stays" data-results aria-busy="true">${skeletonCards(6)}</div>`;
  },

  mount(root, ctx) {
    const state = { criteria: readCriteria(ctx.query), catalogue: [], results: null, error: null };
    const form = root.querySelector('[data-search]');
    const grid = root.querySelector('[data-results]');
    const summaryEl = root.querySelector('[data-summary]');
    const searchError = root.querySelector('[data-search-error]');
    const filter = root.querySelector('[data-filter]');
    const sort = root.querySelector('[data-sort]');
    const reset = root.querySelector('[data-reset]');
    const field = (name) => form.elements.namedItem(name);
    let controller = null;

    const syncUrl = () => {
      const { start, end, guests, q, sort: order } = state.criteria;
      replaceQuery(PATH, { start, end, guests: guests > 1 ? guests : '', q, sort: order === 'priceAsc' ? '' : order });
    };

    const hasDates = () => Boolean(state.criteria.start && state.criteria.end);

    const visible = () => {
      const needle = state.criteria.q.trim().toLocaleLowerCase();
      const source = state.results ?? state.catalogue.filter((apartment) => apartment.maxPeople >= state.criteria.guests);
      return source
        .filter((apartment) => !needle || `${apartment.name} ${apartment.address}`.toLocaleLowerCase().includes(needle))
        .sort(COMPARE[state.criteria.sort]);
    };

    const paint = () => {
      grid.setAttribute('aria-busy', 'false');
      reset.hidden = !(hasDates() || state.criteria.q || state.criteria.guests > 1);
      if (state.error) {
        summaryEl.textContent = '';
        render(grid, errorState(errorCopy(state.error).message));
        return;
      }
      const items = visible();
      const { start, end, guests } = state.criteria;
      render(summaryEl, hasDates()
        ? html`<strong>${t('explore.available', { count: items.length })}</strong><span>${formatRange(start, end)} · ${t('common.guests', { count: guests })}</span>`
        : html`<strong>${t('explore.allStays', { count: items.length })}</strong><span>${t('explore.hintDates')}</span>`);

      if (!items.length) {
        const pool = state.results ?? state.catalogue;
        const copy = !state.catalogue.length && !state.results
          ? { iconName: 'home', title: t('explore.emptyCatalog.title'), body: t('explore.emptyCatalog.body') }
          : pool.length && state.criteria.q
            ? { iconName: 'search', title: t('explore.noMatch.title'), body: t('explore.noMatch.body', { query: state.criteria.q }) }
            : { iconName: 'calendar', title: t('explore.empty.title'), body: t('explore.empty.body') };
        render(grid, emptyState(copy));
      } else {
        render(grid, items.map((apartment) => stayCard(apartment, {
          action: html`<button type="button" class="btn btn--primary btn--sm" data-book="${apartment.id}">${t('explore.book')}</button>`,
        })));
      }
      observeReveals(grid);
    };

    const load = async () => {
      controller?.abort();
      controller = new AbortController();
      grid.setAttribute('aria-busy', 'true');
      render(grid, skeletonCards(6));
      try {
        const { start, end, guests } = state.criteria;
        if (hasDates()) {
          state.results = await bookingService.searchAvailability({ start, end, guests }, { signal: controller.signal });
        } else {
          state.results = null;
          state.catalogue = await bookingService.listApartments({ signal: controller.signal });
        }
        state.error = null;
      } catch (error) {
        if (error?.name === 'AbortError') return;
        state.error = error;
      }
      paint();
    };

    // Filters apply as they change: dates once both are set, guests and text at once.
    const applySearch = () => {
      const start = field('start').value;
      const end = field('end').value;
      const guests = Number(field('guests').value);
      let message = '';
      if (start && !end) return; // waiting for check-out
      if (!start && end) message = t('explore.errors.bothDates');
      else if (start && start < todayIso()) message = t('booking.errors.pastDate');
      else if (start && end <= start) message = t('booking.errors.endAfterStart');
      else if (!Number.isInteger(guests) || guests < 1) message = t('booking.errors.min');
      showAlert(searchError, message);
      if (message) return;
      const datesChanged = start !== state.criteria.start || end !== state.criteria.end;
      state.criteria = { ...state.criteria, start, end, guests };
      syncUrl();
      if (datesChanged || hasDates()) load();
      else paint();
    };

    form.addEventListener('change', (event) => {
      const { name } = event.target;
      if (name === 'start') {
        const start = field('start').value;
        field('end').min = addDays(start || todayIso(), 1);
        if (field('end').value && start && field('end').value <= start) field('end').value = '';
        if (start && !field('end').value) field('end').focus();
      }
      if (name === 'start' || name === 'end' || name === 'guests') applySearch();
    });

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      applySearch();
    });

    let filterTimer;
    filter.addEventListener('input', () => {
      state.criteria.q = filter.value;
      clearTimeout(filterTimer);
      filterTimer = setTimeout(() => { syncUrl(); paint(); }, 120);
    });
    sort.addEventListener('change', () => {
      state.criteria.sort = sort.value;
      syncUrl();
      paint();
    });
    reset.addEventListener('click', () => {
      state.criteria = readCriteria({});
      form.reset();
      field('start').value = '';
      field('end').value = '';
      field('guests').value = '1';
      filter.value = '';
      sort.value = state.criteria.sort;
      showAlert(searchError, '');
      syncUrl();
      load();
    });

    grid.addEventListener('click', async (event) => {
      if (event.target.closest('[data-retry]')) {
        load();
        return;
      }
      const button = event.target.closest('[data-book]');
      if (!button) return;
      const apartment = visible().find((item) => String(item.id) === button.dataset.book);
      if (!apartment) return;
      const booking = await openBookingDialog({
        apartment, session: ctx.session,
        criteria: hasDates() ? state.criteria : { guests: state.criteria.guests },
      });
      if (booking) {
        toast({ title: t('explore.booked', { city: booking.city || booking.apartmentName }), message: `${booking.apartmentName} · ${formatRange(booking.start, booking.end)}` });
        ctx.app.navigate(`/guest/trips?new=${booking.id}`);
      }
    });

    load();
    return () => {
      controller?.abort();
      clearTimeout(filterTimer);
    };
  },
};
