/**
 * Guest bookings, in two scopes:
 *   mine — "My trips": the bookings made under the guest's name;
 *   all  — "All bookings": every booking, as the CLI's `booking view` shows the booker.
 * Both offer `booking change` and `booking cancel` on any active or upcoming stay.
 */
import { html, render } from '../../core/html.js';
import { t } from '../../core/i18n.js';
import { formatMoney, formatRange, relativeDays, sameName, stayStatus } from '../../core/format.js';
import { observeReveals } from '../../core/motion.js';
import { replaceQuery } from '../../core/router.js';
import { HOME } from '../../config.js';
import { bookingService } from '../../services/booking-service.js';
import { pageHead } from '../../ui/chrome.js';
import { avatar, emptyState, errorState, skeletonRows, statusBadge } from '../../ui/components.js';
import { cover } from '../../ui/cover.js';
import { confirmDialog, errorCopy, toast, toastError } from '../../ui/feedback.js';
import { icon } from '../../ui/icons.js';
import { openChangeDialog } from './stay-dialogs.js';

const SCOPES = {
  mine: { path: '/guest/trips', keys: 'trips' },
  all: { path: '/guest/bookings', keys: 'bookings' },
};

function tripCard(booking, highlight, showGuest) {
  const place = [booking.city, booking.country].filter(Boolean).join(', ');
  return html`<article class="trip reveal ${highlight ? 'is-new' : ''}" data-id="${booking.id}">
    <div class="trip__thumb">${cover({ name: booking.apartmentName }, { size: 'sm', monogram: false })}</div>
    <div class="trip__main">
      <h3 class="trip__name">${booking.apartmentName}</h3>
      ${showGuest ? html`<p class="trip__guest">${avatar(booking.guestName, 'sm')}<span>${t('bookings.by', { name: booking.guestName })}</span></p>` : ''}
      <p class="trip__sub">${booking.status === 'ongoing' ? statusBadge('ongoing') : ''}${booking.status === 'upcoming'
        ? html`<span class="trip__countdown">${relativeDays(booking.start)}</span> · ` : ''}${place}</p>
    </div>
    <div class="trip__when">
      <strong>${formatRange(booking.start, booking.end)}</strong>
      <span>${t('common.nights', { count: booking.nights })} · ${t('common.guests', { count: booking.people })}</span>
    </div>
    <p class="trip__total">${formatMoney(booking.total)}</p>
    <div class="trip__actions">${booking.status !== 'past' ? html`
      <button type="button" class="btn btn--soft btn--sm" data-change="${booking.id}">${t('trips.change')}</button>
      <button type="button" class="btn btn--quiet-danger btn--sm" data-cancel="${booking.id}">${t('trips.cancel')}</button>` : ''}
    </div>
  </article>`;
}

function createTripsView(scope) {
  const { path: PATH, keys } = SCOPES[scope];
  return {
    title: () => t(`${keys}.metaTitle`),

    render: (ctx) => html`
      ${pageHead({ title: t(`${keys}.title`) })}
      <div class="segmented" role="group" aria-label="${t('trips.filterLabel')}" data-tabs>
        <button type="button" class="segmented__btn" data-tab="upcoming" aria-pressed="${ctx.query.tab !== 'past'}">${t('trips.upcoming')} <span class="count" data-count="upcoming">·</span></button>
        <button type="button" class="segmented__btn" data-tab="past" aria-pressed="${ctx.query.tab === 'past'}">${t('trips.past')} <span class="count" data-count="past">·</span></button>
      </div>
      <div class="trips" data-list aria-live="polite" aria-busy="true">${skeletonRows(3)}</div>`,

    mount(root, ctx) {
      const state = { tab: ctx.query.tab === 'past' ? 'past' : 'upcoming', bookings: [], error: null, highlight: ctx.query.new ?? null };
      const list = root.querySelector('[data-list]');
      const controller = new AbortController();

      const groups = () => {
        const upcoming = state.bookings.filter((b) => b.status !== 'past').sort((a, b) => a.start.localeCompare(b.start));
        const past = state.bookings.filter((b) => b.status === 'past').sort((a, b) => b.end.localeCompare(a.end));
        return { upcoming, past };
      };

      const paint = () => {
        list.setAttribute('aria-busy', 'false');
        root.querySelectorAll('[data-tab]').forEach((tab) => tab.setAttribute('aria-pressed', String(tab.dataset.tab === state.tab)));
        if (state.error) {
          render(list, errorState(errorCopy(state.error).message));
          return;
        }
        const grouped = groups();
        root.querySelector('[data-count="upcoming"]').textContent = grouped.upcoming.length;
        root.querySelector('[data-count="past"]').textContent = grouped.past.length;
        const items = grouped[state.tab];
        if (!items.length) {
          render(list, state.tab === 'upcoming'
            ? emptyState({
              iconName: 'suitcase', title: t(`${keys}.empty.title`), body: t(`${keys}.empty.body`),
              action: html`<a class="btn btn--primary" href="#${HOME.guest}">${icon('compass', 18)} ${t('trips.empty.cta')}</a>`,
            })
            : emptyState({ iconName: 'clock', title: t(`${keys}.emptyPast.title`), body: t(`${keys}.emptyPast.body`) }));
        } else {
          render(list, items.map((booking) => tripCard(booking, String(booking.id) === state.highlight, scope === 'all')));
        }
        observeReveals(list);
      };

      const load = async () => {
        try {
          const all = await bookingService.listBookings({ signal: controller.signal });
          state.bookings = all
            .filter((booking) => scope === 'all' || sameName(booking.guestName, ctx.session.name))
            .map((booking) => ({ ...booking, status: stayStatus(booking) }));
          state.error = null;
        } catch (error) {
          if (error?.name === 'AbortError') return;
          state.error = error;
        }
        paint();
      };

      root.querySelector('[data-tabs]').addEventListener('click', (event) => {
        const tab = event.target.closest('[data-tab]');
        if (!tab) return;
        state.tab = tab.dataset.tab;
        replaceQuery(PATH, { tab: state.tab === 'past' ? 'past' : '' });
        paint();
      });

      list.addEventListener('click', async (event) => {
        if (event.target.closest('[data-retry]')) {
          load();
          return;
        }
        const changeButton = event.target.closest('[data-change]');
        const cancelButton = event.target.closest('[data-cancel]');
        const id = changeButton?.dataset.change ?? cancelButton?.dataset.cancel;
        const booking = state.bookings.find((item) => String(item.id) === id);
        if (!booking) return;

        if (changeButton) {
          const updated = await openChangeDialog(booking);
          if (updated) {
            state.highlight = String(updated.id);
            toast({ title: t('trips.changed'), message: `${updated.apartmentName} · ${formatRange(updated.start, updated.end)}` });
            load();
          }
          return;
        }

        const confirmed = await confirmDialog({
          title: t('trips.cancelTitle'),
          message: scope === 'all'
            ? t('bookings.cancelBody', { guest: booking.guestName, name: booking.apartmentName, range: formatRange(booking.start, booking.end) })
            : t('trips.cancelBody', { name: booking.apartmentName, range: formatRange(booking.start, booking.end) }),
          confirmLabel: t('trips.cancelConfirm'),
          cancelLabel: t('trips.keep'),
        });
        if (!confirmed) return;
        try {
          await bookingService.cancelBooking({ apartmentName: booking.apartmentName, start: booking.start, end: booking.end });
          toast({ title: t('trips.cancelled'), message: booking.apartmentName });
        } catch (error) {
          toastError(error, { not_found: t('errors.bookingGone') });
        }
        load();
      });

      load();
      return () => controller.abort();
    },
  };
}

export const tripsView = createTripsView('mine');
export const bookingsView = createTripsView('all');
