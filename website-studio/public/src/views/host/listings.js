/** Host: listing catalogue (apartment view, add, update price, remove). */
import { html, render } from '../../core/html.js';
import { t } from '../../core/i18n.js';
import { stayStatus } from '../../core/format.js';
import { observeReveals } from '../../core/motion.js';
import { bookingService } from '../../services/booking-service.js';
import { pageHead } from '../../ui/chrome.js';
import { emptyState, errorState, skeletonCards, stayCard } from '../../ui/components.js';
import { errorCopy } from '../../ui/feedback.js';
import { icon } from '../../ui/icons.js';
import { openListingDialog, openPriceDialog, removeListing } from './listing-dialogs.js';

export const listingsView = {
  title: () => t('host.listings.metaTitle'),

  render: () => html`
    ${pageHead({
      title: t('host.listings.title'),
      actions: html`<button type="button" class="btn btn--primary" data-add>${icon('plus', 18)} ${t('host.listings.add')}</button>`,
    })}
    <div class="toolbar">
      <div class="toolbar__summary" data-summary aria-live="polite"></div>
      <div class="toolbar__controls">
        <label class="input-icon">${icon('search', 16)}<span class="visually-hidden">${t('host.listings.search')}</span>
          <input class="input input--pill" type="search" data-filter placeholder="${t('host.listings.search')}">
        </label>
      </div>
    </div>
    <div class="grid grid--stays" data-grid aria-busy="true">${skeletonCards(3)}</div>`,

  mount(root) {
    const grid = root.querySelector('[data-grid]');
    const filter = root.querySelector('[data-filter]');
    const summaryEl = root.querySelector('[data-summary]');
    const controller = new AbortController();
    const state = { apartments: [], bookings: [], error: null };

    const bookingsFor = (apartment) => state.bookings.filter((booking) => booking.apartmentId === apartment.id);

    const paint = () => {
      grid.setAttribute('aria-busy', 'false');
      if (state.error) {
        summaryEl.textContent = '';
        render(grid, errorState(errorCopy(state.error).message));
        return;
      }
      const needle = filter.value.trim().toLocaleLowerCase();
      const items = state.apartments
        .filter((apartment) => !needle || `${apartment.name} ${apartment.address}`.toLocaleLowerCase().includes(needle))
        .sort((a, b) => a.name.localeCompare(b.name));
      render(summaryEl, html`<strong>${t('host.listings.count', { count: items.length })}</strong>`);

      if (!state.apartments.length) {
        render(grid, emptyState({
          iconName: 'home', title: t('host.listings.empty.title'), body: t('host.listings.empty.body'),
          action: html`<button type="button" class="btn btn--primary" data-add>${icon('plus', 18)} ${t('host.listings.empty.cta')}</button>`,
        }));
      } else if (!items.length) {
        render(grid, emptyState({ iconName: 'search', title: t('explore.noMatch.title'), body: t('explore.noMatch.body', { query: filter.value }) }));
      } else {
        render(grid, items.map((apartment) => {
          const active = bookingsFor(apartment).filter((booking) => stayStatus(booking) !== 'past').length;
          return stayCard(apartment, {
            facts: html`<span title="${t('common.upTo', { count: apartment.maxPeople })}">${icon('users', 15)} ${apartment.maxPeople}<span class="visually-hidden">${t('common.upTo', { count: apartment.maxPeople })}</span></span>
              <span>${icon('calendar', 15)} ${t('host.listings.active', { count: active })}</span>`,
            action: html`<div class="stay__actions">
              <button type="button" class="btn btn--soft btn--sm" data-price="${apartment.id}">${t('host.listings.editPrice')}</button>
              <button type="button" class="btn btn--icon btn--sm btn--quiet-danger" data-remove="${apartment.id}"
                aria-label="${t('host.listings.removeAction')} ${apartment.name}" title="${t('host.listings.removeAction')}">${icon('trash', 16)}</button>
            </div>`,
          });
        }));
      }
      observeReveals(grid);
    };

    const load = async () => {
      try {
        [state.apartments, state.bookings] = await Promise.all([
          bookingService.listApartments({ signal: controller.signal }),
          bookingService.listBookings({ signal: controller.signal }),
        ]);
        state.error = null;
      } catch (error) {
        if (error?.name === 'AbortError') return;
        state.error = error;
      }
      paint();
    };

    filter.addEventListener('input', paint);
    root.addEventListener('click', async (event) => {
      if (event.target.closest('[data-retry]')) return load();
      if (event.target.closest('[data-add]')) {
        if (await openListingDialog()) load();
        return undefined;
      }
      const priceButton = event.target.closest('[data-price]');
      const removeButton = event.target.closest('[data-remove]');
      const id = priceButton?.dataset.price ?? removeButton?.dataset.remove;
      const apartment = state.apartments.find((item) => String(item.id) === id);
      if (!apartment) return undefined;
      if (priceButton && (await openPriceDialog(apartment))) load();
      if (removeButton && (await removeListing(apartment, bookingsFor(apartment).length))) load();
      return undefined;
    });

    load();
    return () => controller.abort();
  },
};
